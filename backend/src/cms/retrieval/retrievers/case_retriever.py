"""Dense, sparse and hybrid retrieval over the cases collection.

`asimilarity_search_with_score` is LangChain's base-class thread offload —
`QdrantVectorStore` implements no async methods of its own. It still keeps the
event loop free, which is what an async caller needs.
"""

import logging

from langchain_core.documents import Document
from langchain_qdrant import RetrievalMode

from cms.config.settings import get_settings
from cms.retrieval.vector_store.qdrant_store import get_vector_store

logger = logging.getLogger(__name__)

# Read once at import: the value is a function default below, and settings are
# process-wide anyway. Tune it with CASE_TOP_K.
DEFAULT_K = get_settings().case_top_k


async def _search(query: str, k: int, mode: RetrievalMode) -> list[tuple[Document, float]]:
    """Top-`k` case chunks for `query` from one retrieval leg."""
    collection = get_settings().qdrant_cases_collection
    store = get_vector_store(collection, mode=mode)

    try:
        hits = await store.asimilarity_search_with_score(query, k=k)
    except Exception:
        logger.exception(
            "Case search failed on '%s' (mode=%s) for query %r", collection, mode, query
        )
        raise

    logger.info(
        "Retrieved %d case chunk(s) from '%s' (mode=%s) for query %r",
        len(hits),
        collection,
        mode,
        query,
    )
    return hits


async def retrieve_cases_dense(query: str, k: int = DEFAULT_K) -> list[tuple[Document, float]]:
    """Semantic leg: cosine over OpenAI embeddings."""
    return await _search(query, k, RetrievalMode.DENSE)


async def retrieve_cases_sparse(query: str, k: int = DEFAULT_K) -> list[tuple[Document, float]]:
    """Lexical leg: BM25 via local fastembed — no API cost."""
    return await _search(query, k, RetrievalMode.SPARSE)


async def retrieve_cases_hybrid(query: str, k: int = DEFAULT_K) -> list[tuple[Document, float]]:
    """Both legs, fused by Qdrant server-side (RRF).

    Scores are RRF values — a third scale again, comparable neither to the dense
    leg's cosine nor the sparse leg's BM25.
    """
    return await _search(query, k, RetrievalMode.HYBRID)
