"""Complaint branch: search the policy corpus with every query analyze_query wrote.
"""

import asyncio
import logging

from langchain_core.documents import Document
from langsmith import traceable

from cms.rag.state import GraphState
from cms.retrieval.rerank.openrouter_reranker import rerank_documents
from cms.retrieval.retrievers.policy_retriever import (
    DEFAULT_TOP_N,
    RERANK_ENABLED,
    retrieve_policies_hybrid,
)

logger = logging.getLogger(__name__)


def merge_hits(results: list[list[tuple[Document, float]]]) -> list[tuple[Document, float]]:
    """One ranked list from the per-query lists, best score per chunk.

    A chunk found by two queries is one chunk, and its scores are RRF values from
    two different searches — same scale, but not one ranking. Keeping the max is
    the simple read: how well this chunk did for the query that liked it most.
    """
    best: dict[str, tuple[Document, float]] = {}
    for hits in results:
        for document, score in hits:
            # chunk_id is set by ingestion; a hand-built Document in a probe need not have one.
            key = document.metadata.get("chunk_id") or document.page_content
            if key not in best or score > best[key][1]:
                best[key] = (document, score)
    return sorted(best.values(), key=lambda hit: hit[1], reverse=True)


async def retrieve_policies_core(
    queries: list[str],
    rerank: bool = RERANK_ENABLED,
    top_n: int = DEFAULT_TOP_N,
) -> list[tuple[Document, float]]:
    """Run `queries` against the policy corpus in parallel, merge, then rerank to `top_n`.

    The per-query searches pass `rerank=False` on purpose: a wide, cheap pool per
    query is the point of the fan-out, and one rerank over the union is both
    cheaper and better than one per query.

    The rerank runs against `queries[0]`, which `build_policy_queries` guarantees
    is the customer's original wording — the rewrites are retrieval aids, and
    ranking the final context by one of them would drift from what was asked.
    """
    if not queries:
        return []

    try:
        results = await asyncio.gather(
            *(retrieve_policies_hybrid(query, rerank=False) for query in queries)
        )
    except Exception:
        logger.exception("Policy retrieval failed for %d query(ies)", len(queries))
        raise

    hits = merge_hits(list(results))
    if not rerank or not hits:
        logger.info(
            "retrieve_policies: %d query(ies) -> %d unique chunk(s)", len(queries), len(hits)
        )
        return hits

    ranked = await rerank_documents(queries[0], hits, top_n)
    logger.info(
        "retrieve_policies: %d query(ies) -> %d unique chunk(s) -> %d after rerank",
        len(queries),
        len(hits),
        len(ranked),
    )
    return ranked


@traceable(name="retrieve_policies")
async def retrieve_policies(state: GraphState) -> dict:
    """The graph node: a partial `GraphState` update."""
    hits = await retrieve_policies_core(state.get("policy_queries", []))
    return {"policy_hits": hits, "no_match": not hits}
