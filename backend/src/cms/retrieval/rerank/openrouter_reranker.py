"""OpenRouter cross-encoder reranking over an already-retrieved candidate pool.
"""

import logging
from functools import lru_cache

from langchain_core.documents import Document

from cms.config.settings import get_settings
from cms.llm.rerank.openrouter_rerank import OpenRouterRerank

logger = logging.getLogger(__name__)

# Voyage itself caps a request at 1000; this is a tighter local guard. Our pools
# are ~20, so anything near this means a caller passed the wrong `k` — better to
# say so than to quietly bill for it.
MAX_DOCUMENTS = 100


@lru_cache
def get_reranker(top_n: int) -> OpenRouterRerank:
    """The reranker for one `top_n`, built once.

    Cached per `top_n` because `OpenRouterRerank` takes it as a field. Safe
    across event loops: the compressor opens a fresh `httpx.AsyncClient` per
    request, which the eval suite's repeated `asyncio.run` depends on.
    """
    settings = get_settings()
    return OpenRouterRerank(
        api_key=settings.open_router_api_key,
        model=settings.openrouter_rerank_model,
        base_url=settings.openrouter_base_url,
        top_n=top_n,
        timeout=settings.openrouter_timeout_seconds,
    )


async def rerank_documents(
    query: str, hits: list[tuple[Document, float]], top_n: int
) -> list[tuple[Document, float]]:
    """Reorder `hits` by relevance to `query` and keep the best `top_n`.

    The float slot comes back as the reranker's relevance score, not the cosine,
    BM25 or RRF value it replaces.
    """
    if not hits:
        return []

    documents = [document for document, _ in hits]
    if len(documents) > MAX_DOCUMENTS:
        raise ValueError(
            f"OpenRouter reranks at most {MAX_DOCUMENTS} documents at once, got {len(documents)}"
        )

    try:
        ranked = await get_reranker(top_n).acompress_documents(documents, query)
    except Exception:
        # Not caught and downgraded to "return the retrieval order": that would
        # score as a working reranker in the evals while doing nothing.
        logger.exception(
            "OpenRouter rerank failed on %d document(s) for query %r", len(documents), query
        )
        raise

    return [(document, document.metadata["relevance_score"]) for document in ranked]
