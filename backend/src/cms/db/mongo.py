"""The Mongo client and the LangGraph checkpointer that stores chat transcripts.

`MongoDBSaver` needs a sync `MongoClient` and runs each call on a thread. Both are built lazily.
"""

import logging
from functools import lru_cache

from langgraph.checkpoint.mongodb import MongoDBSaver
from pymongo import MongoClient

from cms.config.settings import get_settings

logger = logging.getLogger(__name__)


@lru_cache
def get_mongo_client() -> MongoClient:
    """Mongo client, constructed once per process.

    `MongoClient` opens no socket in its constructor, so a Mongo that is down
    surfaces on first use rather than at startup.
    """
    settings = get_settings()
    try:
        client = MongoClient(
            settings.mongo_url,
            serverSelectionTimeoutMS=settings.mongo_timeout_ms,
            connectTimeoutMS=settings.mongo_timeout_ms,
        )
    except Exception:
        logger.exception("Failed to construct Mongo client for %s", settings.mongo_url)
        raise
    logger.debug("Mongo client constructed for %s", settings.mongo_url)
    return client


async def close_mongo_client() -> None:
    """Close the Mongo client, if it was built."""
    if get_mongo_client.cache_info().currsize == 0:
        return
    get_mongo_client().close()
    logger.info("Mongo client closed")


@lru_cache
def get_checkpointer() -> MongoDBSaver | None:
    """The graph's checkpointer, or None when chat memory is turned off.

    None compiles the graph exactly as it was before Mongo existed: chat still
    answers, nothing is stored, and the replay endpoint returns an empty list.
    """
    settings = get_settings()
    if not settings.chat_memory_enabled:
        logger.warning("Chat memory is disabled; conversations will not be stored")
        return None

    try:
        # Collection names are left at the library's defaults (`checkpoints` and
        # `checkpoint_writes`), and so is `ttl` — transcripts are kept forever
        # while this is the only copy of them.
        saver = MongoDBSaver(get_mongo_client(), db_name=settings.mongo_db_name)
    except Exception:
        logger.exception("Failed to build the Mongo checkpointer for db %s", settings.mongo_db_name)
        raise
    logger.info("Chat memory enabled: checkpointing to Mongo db %s", settings.mongo_db_name)
    return saver
