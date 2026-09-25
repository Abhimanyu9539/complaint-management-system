"""Lookup branch: find the past cases the agent asked about.
"""

import logging

from langchain_core.documents import Document
from langsmith import traceable

from cms.config.settings import get_settings
from cms.rag.state import GraphState
from cms.retrieval.rerank.openrouter_reranker import rerank_documents
from cms.retrieval.retrievers.case_retriever import retrieve_cases_hybrid

logger = logging.getLogger(__name__)


async def retrieve_lookup_cases_core(query: str) -> list[tuple[Document, float]]:
    """A wide hybrid pool of cases, reranked against `query`, then gated on the best score.

    Unlike the complaint branch's top-4, a lookup can ask for a list, so the pool is
    wider and the reranker decides what is relevant. The gate works like the policy
    one: if even the best case scores below the threshold, nothing is returned.
    With reranking off there is no gate — RRF scores are on another scale.
    """
    settings = get_settings()
    hits = await retrieve_cases_hybrid(query, k=settings.lookup_case_pool_k)
    if not settings.rerank_enabled or not hits:
        logger.info("lookup_retrieve_cases: %d chunk(s), not reranked", len(hits))
        return hits[: settings.lookup_case_top_n]

    ranked = await rerank_documents(query, hits, settings.lookup_case_top_n)
    best = ranked[0][1] if ranked else 0.0
    logger.info(
        "lookup_retrieve_cases: %d chunk(s) -> %d after rerank, best score %.3f (gate %.2f)",
        len(hits),
        len(ranked),
        best,
        settings.lookup_case_relevance_threshold,
    )
    if best < settings.lookup_case_relevance_threshold:
        logger.info("lookup_retrieve_cases: best score below the gate, no case match")
        return []
    return ranked


@traceable(name="lookup_retrieve_cases")
async def lookup_retrieve_cases(state: GraphState) -> dict:
    """The graph node: a partial `GraphState` update.

    Always runs, so `lookup_join_retrieval` has both inputs; a policies-only lookup
    returns empty without searching. Searches with the agent's own wording.
    """
    if state.get("lookup_target") == "policies":
        logger.info("lookup_retrieve_cases: policies-only lookup, skipped")
        return {"case_hits": []}

    query = state["query"]
    try:
        hits = await retrieve_lookup_cases_core(query)
    except Exception:
        logger.exception("Lookup case retrieval failed for query %r", query)
        raise
    return {"case_hits": hits}
