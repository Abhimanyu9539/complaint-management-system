"""Dense, sparse and hybrid retrieval over the policies collection.

`asimilarity_search_with_score` is LangChain's base-class thread offload —
`QdrantVectorStore` implements no async methods of its own. It still keeps the
event loop free, which is what an async caller needs.
"""

import logging

from langchain_core.documents import Document
from langchain_qdrant import RetrievalMode
from qdrant_client import models

from cms.config.settings import get_settings
from cms.retrieval.vector_store.qdrant_store import get_vector_store

logger = logging.getLogger(__name__)

DEFAULT_K = 10
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


async def _search(query: str, k: int, mode: RetrievalMode) -> list[tuple[Document, float]]:
    """Top-`k` published policy chunks for `query` from one retrieval leg."""
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
        "Retrieved %d policy chunk(s) from '%s' (mode=%s) for query %r",
        len(hits),
        collection,
        mode,
        query,
    )
    return hits


async def retrieve_policies_dense(query: str, k: int = DEFAULT_K) -> list[tuple[Document, float]]:
    """Semantic leg: cosine over OpenAI embeddings."""
    return await _search(query, k, RetrievalMode.DENSE)


async def retrieve_policies_sparse(query: str, k: int = DEFAULT_K) -> list[tuple[Document, float]]:
    """Lexical leg: BM25 via local fastembed — no API cost."""
    return await _search(query, k, RetrievalMode.SPARSE)


async def retrieve_policies_hybrid(query: str, k: int = DEFAULT_K) -> list[tuple[Document, float]]:
    """Both legs, fused by Qdrant server-side (RRF).

    Scores are RRF values — a third scale again, comparable neither to the dense
    leg's cosine nor the sparse leg's BM25.
    """
    return await _search(query, k, RetrievalMode.HYBRID)
