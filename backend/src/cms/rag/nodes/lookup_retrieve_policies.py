"""Lookup branch: search the policy corpus with every query analyze_query wrote.
"""

import asyncio
import logging

from langchain_core.documents import Document
from langsmith import traceable

from cms.config.settings import get_settings
from cms.rag.state import GraphState
from cms.retrieval.rerank.openrouter_reranker import rerank_documents
from cms.retrieval.retrievers.policy_retriever import retrieve_policies_hybrid

logger = logging.getLogger(__name__)


def _merge_hits(results: list[list[tuple[Document, float]]]) -> list[tuple[Document, float]]:
    """One ranked list from the per-query lists, keeping each chunk's best score."""
    best: dict[str, tuple[Document, float]] = {}
    for hits in results:
        for document, score in hits:
            key = document.metadata.get("chunk_id") or document.page_content
            if key not in best or score > best[key][1]:
                best[key] = (document, score)
    return sorted(best.values(), key=lambda hit: hit[1], reverse=True)


async def retrieve_lookup_policies_core(queries: list[str]) -> list[tuple[Document, float]]:
    """Every query against the policy corpus, merged, reranked once, then gated on the best score.

    Same flow and settings as the complaint branch's policy search, kept separate so
    each branch can change on its own. The rerank runs against `queries[0]`, the
    agent's own wording; the rewrites only widen the pool.
    """
    settings = get_settings()
    if not queries:
        return []

    results = await asyncio.gather(
        *(retrieve_policies_hybrid(query, rerank=False) for query in queries)
    )
    hits = _merge_hits(list(results))
    if not settings.rerank_enabled or not hits:
        logger.info("lookup_retrieve_policies: %d chunk(s), not reranked", len(hits))
        return hits

    ranked = await rerank_documents(queries[0], hits, settings.policy_rerank_top_n)
    best = ranked[0][1] if ranked else 0.0
    logger.info(
        "lookup_retrieve_policies: %d query(ies) -> %d chunk(s) -> %d after rerank, "
        "best score %.3f (gate %.2f)",
        len(queries),
        len(hits),
        len(ranked),
        best,
        settings.policy_relevance_threshold,
    )
    if best < settings.policy_relevance_threshold:
        logger.info("lookup_retrieve_policies: best score below the gate, no policy match")
        return []
    return ranked


@traceable(name="lookup_retrieve_policies")
async def lookup_retrieve_policies(state: GraphState) -> dict:
    """The graph node: a partial `GraphState` update.

    Always runs, so `lookup_join_retrieval` has both inputs; a cases-only lookup
    returns empty without searching.
    """
    if state.get("lookup_target") == "cases":
        logger.info("lookup_retrieve_policies: cases-only lookup, skipped")
        return {"policy_hits": []}

    queries = state.get("policy_queries", [])
    try:
        hits = await retrieve_lookup_policies_core(queries)
    except Exception:
        logger.exception("Lookup policy retrieval failed for %d query(ies)", len(queries))
        raise
    return {"policy_hits": hits}
