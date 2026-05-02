"""Retrieved chunks -> one numbered context block plus the citations for it.

The augmentation half of RAG. No LLM call, no I/O — given the same hits it
returns the same string, so it is cheap to test and cheap to eyeball
(`cms-graph ... --context`).
"""

import logging

from langchain_core.documents import Document

from cms.config.settings import get_settings
from cms.ingestion.transform.chunker import count_tokens
from cms.schemas.generation import Citation

logger = logging.getLogger(__name__)

DEFAULT_CONTEXT_TOKENS = get_settings().generation_context_tokens

BLOCK_SEPARATOR = "\n\n"


def _section(document: Document) -> str:
    """The heading breadcrumb `chunk_policy` prepended to this chunk.

    It is the first line of the chunk text, not a metadata field — see
    `ingestion/transform/chunker.py`. A chunk from a policy with no headings has
    no breadcrumb, and the first line is body text; that is still the most
    useful one-line label we have for it.
    """
    return document.page_content.split("\n", 1)[0].strip()


def build_context(
    hits: list[tuple[Document, float]],
    budget_tokens: int = DEFAULT_CONTEXT_TOKENS,
) -> tuple[str, list[Citation]]:
    """Format `hits` (best first) as `[1] ... [n]` blocks within `budget_tokens`.

    Returns the block text and one `Citation` per chunk that made it in, with
    matching markers — a draft's `[3]` is `citations[2]`.

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

    for marker, (document, _score) in enumerate(hits, start=1):
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
            )
        )

    logger.info("build_context: %d chunk(s), ~%d tokens", len(blocks), used)
    return BLOCK_SEPARATOR.join(blocks), citations
