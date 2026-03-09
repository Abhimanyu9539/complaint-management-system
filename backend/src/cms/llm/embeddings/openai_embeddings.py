"""Dense embeddings, via OpenAI.

Wrapped in LangChain's `OpenAIEmbeddings` rather than the raw OpenAI client so
LangSmith traces every embedding call for free — cost and latency of the
ingestion path show up in the same place as the chat traces.

The sparse (BM25) half of hybrid retrieval deliberately does **not** live here:
it is a lexical index computed locally by fastembed, not a model API, and it
belongs with the store that scores it — see
`retrieval.vector_store.qdrant_store`.
"""

import logging
from functools import lru_cache

from langchain_openai import OpenAIEmbeddings

from cms.config.settings import get_settings

logger = logging.getLogger(__name__)


@lru_cache
def get_dense_embeddings() -> OpenAIEmbeddings:
    """The dense embedder, constructed once per process."""
    settings = get_settings()
    try:
        embeddings = OpenAIEmbeddings(
            model=settings.embedding_model,
            api_key=settings.openai_api_key,
        )
    except Exception:
        logger.exception(
            "Failed to construct dense embeddings (model=%s)", settings.embedding_model
        )
        raise
    logger.debug("Dense embeddings ready: %s", settings.embedding_model)
    return embeddings
