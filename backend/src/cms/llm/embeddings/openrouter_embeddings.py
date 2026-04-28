"""Dense embeddings, via OpenRouter.
"""

import logging
from functools import lru_cache

from langchain_openai import OpenAIEmbeddings

from cms.config.settings import get_settings

logger = logging.getLogger(__name__)


# OpenRouter has no embeddings class of its own, but its endpoint is
# OpenAI-compatible — so `OpenAIEmbeddings` with the gateway's base URL is the
# whole swap, and LangSmith still traces the calls.
#
# Matched with `in` rather than a prefix check: only the v3 models accept
# `dimensions`, and the slug arrives gateway-prefixed ("openai/text-embedding-3-small").
_TRUNCATABLE_MARKER = "text-embedding-3"


@lru_cache
def get_dense_embeddings() -> OpenAIEmbeddings:
    """The dense embedder, constructed once per process.

    `embedding_dims` is applied here as well as to the collection, so the two
    cannot disagree — a mismatch would otherwise surface as a Qdrant write error.
    """
    settings = get_settings()
    model = settings.openrouter_embedding_model
    truncation = (
        {"dimensions": settings.embedding_dims} if _TRUNCATABLE_MARKER in model else {}
    )

    try:
        embeddings = OpenAIEmbeddings(
            model=model,
            api_key=settings.open_router_api_key,
            base_url=settings.openrouter_base_url,
            **truncation,
        )
    except Exception:
        logger.exception("Failed to construct dense embeddings (model=%s)", model)
        raise
    logger.debug(
        "Dense embeddings ready: %s (%s dims)",
        model,
        settings.embedding_dims if truncation else "native",
    )
    return embeddings
