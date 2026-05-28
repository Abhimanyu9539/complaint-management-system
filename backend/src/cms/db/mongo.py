"""The Mongo handle and the LangGraph checkpointer built on it.

Mongo stores chat transcripts because Supabase cannot yet: `chat_sessions` and
`messages` are RLS'd to `auth.uid()` and this API holds the service-role key,
which bypasses RLS. Mongo has no RLS, so the transcript lives here until auth
lands. See `cms.rag.nodes.record_turn` for what is written.

`MongoDBSaver` takes a *synchronous* `MongoClient` — the async saver was removed
in langgraph-checkpoint-mongodb 0.5.0. Its `aget_tuple`/`aput` run the blocking
calls on a thread executor, and `MongoClient` is thread-safe, so the event loop
is never blocked inside the graph. Unlike the Supabase client in `session.py`,
this one is not bound to an event loop.

Both factories are cached but lazy: nothing connects at import time, so a worker
forked by uvicorn builds its own client rather than inheriting a broken socket.
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
