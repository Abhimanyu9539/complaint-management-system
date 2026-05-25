"""Retrieved chunks -> one numbered context block plus the citations for it.

The augmentation half of RAG. No LLM call, no I/O — given the same hits it
returns the same string, so it is cheap to test and cheap to eyeball
(`cms-graph ... --context`).
"""

import logging
import re

from langchain_core.documents import Document

from cms.config.settings import get_settings
from cms.ingestion.transform.chunker import count_tokens
from cms.schemas.generation import Citation, DocType

logger = logging.getLogger(__name__)

DEFAULT_CONTEXT_TOKENS = get_settings().generation_context_tokens
SNIPPET_CHARS = get_settings().citation_snippet_chars

BLOCK_SEPARATOR = "\n\n"

# The `[3]` markers the draft cites with — the same shape `build_context` writes.
MARKER_PATTERN = re.compile(r"\[(\d+)\]")


def _section(document: Document) -> str:
    """The heading breadcrumb `chunk_policy` prepended to this chunk.

    It is the first line of the chunk text, not a metadata field — see
    `ingestion/transform/chunker.py`. A chunk from a policy with no headings has
    no breadcrumb, and the first line is body text; that is still the most
    useful one-line label we have for it.
    """
    return document.page_content.split("\n", 1)[0].strip()


def _snippet(document: Document) -> str:
    """The chunk body under the breadcrumb, trimmed for the UI's sources panel.

    Drops the first line because `_section` already shows it; a chunk that is a
    single line has no body to drop, so it falls back to the whole thing.
    """
    parts = document.page_content.split("\n", 1)
    body = parts[1].strip() if len(parts) > 1 else ""
    return (body or document.page_content.strip())[:SNIPPET_CHARS]


def build_context(
    hits: list[tuple[Document, float]],
    budget_tokens: int = DEFAULT_CONTEXT_TOKENS,
    start: int = 1,
    doc_type: DocType = "policy",
) -> tuple[str, list[Citation]]:
    """Format `hits` (best first) as `[start] ... [n]` blocks within `budget_tokens`.

    Returns the block text and one `Citation` per chunk that made it in, with
    matching markers — with the default `start`, a draft's `[3]` is `citations[2]`.

    Scores are dropped on purpose: they are the reranker's, on its own scale,
    and showing a model a number it cannot calibrate invites it to reason about
    confidence it has no basis for.

    The budget stops *before* the first block that would exceed it rather than
    truncating mid-chunk — half a policy clause is worse than no clause, since
    the missing half is exactly where the exception usually lives. Note that
    `count_tokens` returns 0 on tokenizer failure rather than raising, so a
    broken tokenizer fails open (everything fits) rather than starving the
    context. That is the right direction for a guard, but a 0 there is not a
    real measurement.
    """
    if not hits:
        logger.info("build_context: no hits, empty context")
        return "", []

    blocks: list[str] = []
    citations: list[Citation] = []
    used = 0

    for marker, (document, _score) in enumerate(hits, start=start):
        metadata = document.metadata
        block = f"[{marker}] {metadata.get('title', 'Untitled')}\n{document.page_content}"

        cost = count_tokens(block)
        if used + cost > budget_tokens:
            logger.info(
                "build_context: budget %d tokens reached, keeping %d of %d chunk(s)",
                budget_tokens,
                len(blocks),
                len(hits),
            )
            break

        used += cost
        blocks.append(block)
        citations.append(
            Citation(
                marker=marker,
                doc_id=str(metadata.get("doc_id", "")),
                chunk_id=str(metadata.get("chunk_id", "")),
                title=str(metadata.get("title", "Untitled")),
                section=_section(document),
                snippet=_snippet(document),
                doc_type=doc_type,
            )
        )

    logger.info("build_context: %d %s chunk(s), ~%d tokens", len(blocks), doc_type, used)
    return BLOCK_SEPARATOR.join(blocks), citations


def build_generation_context(
    policy_hits: list[tuple[Document, float]],
    case_hits: list[tuple[Document, float]],
) -> tuple[str, str, list[Citation]]:
    """Policy block and case block on one marker sequence: cases number on from the last policy.

    Returns `(policy_context, case_context, citations)`. One sequence means a
    draft's `[n]` is unambiguous and `used_citations` needs no change.
    """
    policy_context, policy_citations = build_context(policy_hits)
    case_context, case_citations = build_context(
        case_hits, start=len(policy_citations) + 1, doc_type="case"
    )
    return policy_context, case_context, policy_citations + case_citations


def used_citations(draft: str, citations: list[Citation]) -> list[Citation]:
    """The subset of `citations` the draft actually cited, in marker order.

    The model is offered 12 chunks and typically leans on a handful; showing the
    agent all 12 as sources would misrepresent what the draft rests on.

    Markers are never renumbered — `[3]` in the prose has to keep pointing at
    `marker=3`, so this filters and nothing else.

    The two warnings below are the cheapest groundedness signal available: no
    judge, no second model call, just what the draft cites versus what it was
    given. Neither is fatal — this returns the best mapping it can either way,
    because a draft with a bad reference is still worth showing to an agent who
    can see the citations next to it.
    """
    if not citations:
        return []

    markers = {int(marker) for marker in MARKER_PATTERN.findall(draft)}
    if not markers:
        logger.warning("used_citations: the draft cites nothing; it may be ungrounded")
        return []

    by_marker = {citation.marker: citation for citation in citations}
    unknown = markers - by_marker.keys()
    if unknown:
        logger.warning(
            "used_citations: draft cites %s, but only %d chunk(s) were provided",
            sorted(unknown),
            len(citations),
        )

    return [by_marker[marker] for marker in sorted(markers & by_marker.keys())]
