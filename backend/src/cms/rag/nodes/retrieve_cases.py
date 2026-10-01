"""Complaint branch: find past resolved cases similar to the customer's complaint.
"""

import logging

from langchain_core.documents import Document
from langsmith import traceable

from cms.config.settings import get_settings
from cms.rag.state import GraphState
from cms.retrieval.retrievers.case_retriever import retrieve_cases_reranked

logger = logging.getLogger(__name__)


async def retrieve_cases_core(query: str) -> list[tuple[Document, float]]:
    """A wide hybrid pool of cases, reranked against `query`, then filtered case by case.

    Unlike the lookup branch's best-score gate, every case below
    `case_relevance_threshold` is dropped, so an unrelated case cannot ride along
    with a strong one. With reranking off there is no filter — RRF scores are on
    another scale.
    """
    settings = get_settings()
    hits = await retrieve_cases_reranked(query, settings.case_pool_k, settings.case_top_k)
    if not settings.rerank_enabled:
        logger.info("retrieve_cases: %d case chunk(s), not reranked", len(hits))
        return hits

    threshold = settings.case_relevance_threshold
    kept = [hit for hit in hits if hit[1] >= threshold]
    best = hits[0][1] if hits else 0.0
    logger.info(
        "retrieve_cases: pool k=%d -> %d after rerank -> %d kept, best score %.3f (floor %.2f)",
        settings.case_pool_k,
        len(hits),
        len(kept),
        best,
        threshold,
    )
    return kept


@traceable(name="retrieve_cases")
async def retrieve_cases(state: GraphState) -> dict:
    """The graph node: a partial `GraphState` update.

    Searches with the customer's own wording, not `policy_queries` — cases are
    stored as complaint text, so the original query is the closer match. The
    scores on the hits are rerank scores, which `find_precedents` reuses.
    """
    query = state["query"]
    try:
        hits = await retrieve_cases_core(query)
    except Exception:
        logger.exception("Case retrieval failed for query %r", query)
        raise

    logger.info("retrieve_cases: %d case chunk(s) for %r", len(hits), query)
    return {"case_hits": hits}
