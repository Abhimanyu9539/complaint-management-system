"""Chat completions, via OpenRouter
"""

import logging
from functools import lru_cache

from langchain_openrouter import ChatOpenRouter

from cms.config.settings import get_settings

logger = logging.getLogger(__name__)


@lru_cache
def get_chat_model(model: str) -> ChatOpenRouter:
    """The chat client for one model name, constructed once per process."""
    settings = get_settings()
    try:
        chat_model = ChatOpenRouter(model=model, api_key=settings.open_router_api_key)
    except Exception:
        logger.exception("Failed to construct chat model (model=%s)", model)
        raise
    logger.debug("Chat model ready: %s", model)
    return chat_model


if __name__ == "__main__":
    result = get_chat_model(model = get_settings().openrouter_model_cheap).invoke("What is Gen AI? Explain in simple terms")
    print(result.content)
