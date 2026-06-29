"""Ticket-graph node: offer a similar past case's department answer as a source the drafter can cite.
"""

import logging

from langchain_core.documents import Document
from langsmith import traceable

from cms.config.settings import get_settings
from cms.rag.ticket_state import TicketState
from cms.retrieval.rerank.openrouter_reranker import rerank_documents

logger = logging.getLogger(__name__)

# The labels `build_case_text` puts around a case's department answer.
GUIDANCE_LABEL = "DEPARTMENT GUIDANCE:"
RESOLUTION_LABEL = "RESOLUTION:"


def case_guidance(text: str) -> str | None:
    """The department guidance section of a case chunk, or None if it has none."""
    _, found, rest = text.partition(GUIDANCE_LABEL)
    if not found:
        return None
    return rest.split(RESOLUTION_LABEL, 1)[0].strip() or None


def precedent_hit(document: Document, score: float) -> tuple[Document, float]:
    """A case's department answer as a hit shaped like `context.guidance_hit`, keeping the rerank score."""
    metadata = document.metadata
    title = get_settings().precedent_title_template.format(case=metadata.get("title", "past case"))
    precedent = Document(
        page_content=f"Department guidance\n{case_guidance(document.page_content)}",
        metadata={
            "title": title,
            "doc_id": metadata.get("doc_id", ""),
            "chunk_id": metadata.get("chunk_id", ""),
            "department_id": metadata.get("department", ""),
            "doc_type": "guidance",
        },
    )
    return precedent, score


@traceable(name="find_precedents")
async def find_precedents(state: TicketState) -> dict:
    """The ticket-graph node: past cases whose department answer fits this complaint closely enough.

    Only the retrieved cases that carry a department answer are reranked against
    the complaint; those at or above `precedent_relevance_threshold` are kept.
    A failed rerank raises, and the graph records it and drafts without them.
    """
    settings = get_settings()
    candidates = [hit for hit in state.get("case_hits", []) if case_guidance(hit[0].page_content)]
    if not candidates or not settings.precedents_enabled or not settings.rerank_enabled:
        logger.info(
            "find_precedents: skipped (%d candidate(s), precedents_enabled=%s, rerank_enabled=%s)",
            len(candidates),
            settings.precedents_enabled,
            settings.rerank_enabled,
        )
        return {"precedent_hits": []}

    threshold = settings.precedent_relevance_threshold
    ranked = await rerank_documents(state["query"], candidates, len(candidates))
    precedents = []
    for document, score in ranked:
        kept = score >= threshold
        logger.info(
            "find_precedents: %s scored %.3f (threshold %.2f), %s, for %r",
            document.metadata.get("title"),
            score,
            threshold,
            "kept" if kept else "dropped",
            state["query"][:60],
        )
        if kept:
            precedents.append(precedent_hit(document, score))
    return {"precedent_hits": precedents}
