"""Dense embeddings from OpenAI directly, through LangChain so LangSmith traces each call."""

import logging
from functools import lru_cache

from langchain_openai import OpenAIEmbeddings

from cms.config.settings import get_settings

logger = logging.getLogger(__name__)


# Only the v3 models accept `dimensions` (it truncates the output); ada-002
# rejects the parameter outright, so it is passed conditionally.
_TRUNCATABLE_PREFIX = "text-embedding-3"


@lru_cache
def get_dense_embeddings() -> OpenAIEmbeddings:
    """The dense embedder, constructed once per process.

    `embedding_dims` is applied here as well as to the collection, so the two
    cannot disagree — a mismatch would otherwise surface as a Qdrant write error.
    """
    settings = get_settings()
    truncation = (
        {"dimensions": settings.embedding_dims}
        if settings.embedding_model.startswith(_TRUNCATABLE_PREFIX)
        else {}
    )

    try:
        embeddings = OpenAIEmbeddings(
            model=settings.embedding_model,
            api_key=settings.openai_api_key,
            **truncation,
        )
    except Exception:
        logger.exception(
            "Failed to construct dense embeddings (model=%s)", settings.embedding_model
        )
        raise
    logger.debug(
        "Dense embeddings ready: %s (%s dims)",
        settings.embedding_model,
        settings.embedding_dims if truncation else "native",
    )
    return embeddings
