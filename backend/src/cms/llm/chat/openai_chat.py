"""Chat completions, via OpenAI.

Wrapped in LangChain's `ChatOpenAI` rather than the raw OpenAI client for the
same reason as `llm/embeddings/openai_embeddings.py`: LangSmith traces every
call for free when the LangChain wrapper is used.

Unlike the embedder, there is no single model — build.md's node table
deliberately assigns a cheap model to classification/grading nodes and the
main model to `generate`, the only customer-visible prose. `get_chat_model`
takes the model name as a parameter so both live behind one cached factory,
one client per `(model, process)`, the same shape `qdrant_store.get_vector_store`
uses for `(collection_name, mode)`.
"""

import logging
from functools import lru_cache

from langchain_openai import ChatOpenAI

from cms.config.settings import get_settings

logger = logging.getLogger(__name__)


@lru_cache
def get_chat_model(model: str) -> ChatOpenAI:
    """The chat client for one model name, constructed once per process."""
    settings = get_settings()
    try:
        chat_model = ChatOpenAI(model=model, api_key=settings.openai_api_key)
    except Exception:
        logger.exception("Failed to construct chat model (model=%s)", model)
        raise
    logger.debug("Chat model ready: %s", model)
    return chat_model
