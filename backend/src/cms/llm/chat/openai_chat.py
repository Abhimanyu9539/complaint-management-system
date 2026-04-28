"""Chat completions, via OpenAI.
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
