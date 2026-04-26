"""Dense, sparse and hybrid retrieval over the policies collection.
"""

import logging

from langchain_core.documents import Document
from langchain_qdrant import RetrievalMode
from qdrant_client import models

from cms.config.settings import get_settings
from cms.retrieval.rerank.openrouter_reranker import rerank_documents
from cms.retrieval.vector_store.qdrant_store import get_vector_store

logger = logging.getLogger(__name__)

# Read once at import: these are function defaults below, and settings are
# process-wide anyway. Tune with POLICY_TOP_K, POLICY_RERANK_TOP_N, RERANK_ENABLED.
DEFAULT_K = get_settings().policy_top_k
DEFAULT_TOP_N = get_settings().policy_rerank_top_n
RERANK_ENABLED = get_settings().rerank_enabled
PUBLISHED = "published"

# One shared filter
PUBLISHED_FILTER = models.Filter(
    must=[
        models.FieldCondition(
            key="metadata.lifecycle",
            match=models.MatchValue(value=PUBLISHED),
        )
    ]
)


async def _search(
    query: str, k: int, mode: RetrievalMode, rerank: bool, top_n: int
) -> list[tuple[Document, float]]:
    """Top-`k` published policy chunks for `query`, optionally reranked to `top_n`."""
    collection = get_settings().qdrant_policies_collection
    store = get_vector_store(collection, mode=mode)

    try:
        hits = await store.asimilarity_search_with_score(
            query, k=k, filter=PUBLISHED_FILTER
        )
    except Exception:
        logger.exception(
            "Policy search failed on '%s' (mode=%s) for query %r", collection, mode, query
        )
        raise

    # An empty result is a plausible-looking answer, so say so out loud: it means
    # either nothing is indexed yet or no chunk is `published`.
    logger.info(
        "Retrieved %d policy chunk(s) from '%s' (mode=%s, rerank=%s) for query %r",
        len(hits),
        collection,
        mode,
        rerank,
        query,
    )
    if not rerank:
        return hits

    ranked = await rerank_documents(query, hits, top_n)
    logger.info("Reranked %d policy chunk(s) down to %d", len(hits), len(ranked))
    return ranked


async def retrieve_policies_dense(
    query: str,
    k: int = DEFAULT_K,
    rerank: bool = RERANK_ENABLED,
    top_n: int = DEFAULT_TOP_N,
) -> list[tuple[Document, float]]:
    """Semantic leg: cosine over OpenAI embeddings."""
    return await _search(query, k, RetrievalMode.DENSE, rerank, top_n)


async def retrieve_policies_sparse(
    query: str,
    k: int = DEFAULT_K,
    rerank: bool = RERANK_ENABLED,
    top_n: int = DEFAULT_TOP_N,
) -> list[tuple[Document, float]]:
    """Lexical leg: BM25 via local fastembed — no API cost."""
    return await _search(query, k, RetrievalMode.SPARSE, rerank, top_n)


async def retrieve_policies_hybrid(
    query: str,
    k: int = DEFAULT_K,
    rerank: bool = RERANK_ENABLED,
    top_n: int = DEFAULT_TOP_N,
) -> list[tuple[Document, float]]:
    """Both legs, fused by Qdrant server-side (RRF).

    Unreranked the scores are RRF values — a third scale again, comparable neither
    to the dense leg's cosine nor the sparse leg's BM25. Reranked they are the
    reranker's relevance scores, a fourth.
    """
    return await _search(query, k, RetrievalMode.HYBRID, rerank, top_n)
