"""Voyage cross-encoder reranking over an already-retrieved candidate pool."""

import logging
from functools import lru_cache

from langchain_core.documents import Document
from langchain_voyageai import VoyageAIRerank

from cms.config.settings import get_settings

logger = logging.getLogger(__name__)

# Voyage itself caps a request at 1000; this is a tighter local guard. Our pools
# are ~20, so anything near this means a caller passed the wrong `k` — better to
# say so than to quietly bill for it.
MAX_DOCUMENTS = 100


@lru_cache
def get_reranker(top_n: int) -> VoyageAIRerank:
    """The reranker for one `top_n`, built once.

    Cached per `top_n` because `VoyageAIRerank` takes it as a constructor field.
    Safe across event loops: `voyageai.AsyncClient` opens a fresh aiohttp session
    per request, which the eval suite's repeated `asyncio.run` depends on.
    """
    settings = get_settings()
    return VoyageAIRerank(
        model=settings.rerank_model,
        api_key=settings.voyage_api_key,
        top_k=top_n,
    )


async def rerank_documents(
    query: str, hits: list[tuple[Document, float]], top_n: int
) -> list[tuple[Document, float]]:
    """Reorder `hits` by Voyage relevance to `query` and keep the best `top_n`.

    The float slot comes back as a Voyage relevance score, not the cosine, BM25 or
    RRF value it replaces.
    """
    if not hits:
        return []

    documents = [document for document, _ in hits]
    if len(documents) > MAX_DOCUMENTS:
        raise ValueError(
            f"Voyage reranks at most {MAX_DOCUMENTS} documents at once, got {len(documents)}"
        )

    try:
        ranked = await get_reranker(top_n).acompress_documents(documents, query)
    except Exception:
        # Not caught and downgraded to "return the retrieval order": that would
        # score as a working reranker in the evals while doing nothing.
        logger.exception(
            "Voyage rerank failed on %d document(s) for query %r", len(documents), query
        )
        raise

    return [(document, document.metadata["relevance_score"]) for document in ranked]
