"""The app's lifespan: load the local models before serving, close the network clients after."""

import asyncio
import logging
import time
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI

from cms.config.settings import get_settings
from cms.db.mongo import close_mongo_client
from cms.db.session import close_supabase
from cms.guardrails.guards import get_case_scrubber, get_input_guard, get_lookup_guard, get_output_guard
from cms.retrieval.vector_store.qdrant_store import close_qdrant_clients, get_sparse_embeddings

logger = logging.getLogger(__name__)

CLOSERS = (close_qdrant_clients, close_supabase, close_mongo_client)


def warm_up_models() -> None:
    """Load BM25 and the Presidio guards (spaCy) now, not on the first request. Raises on failure."""
    # The case scrubber runs even with guardrails off; the other guards only with them on.
    loaders = [get_sparse_embeddings, get_case_scrubber]
    if get_settings().guardrails_enabled:
        loaders += [get_input_guard, get_output_guard, get_lookup_guard]

    for loader in loaders:
        started = time.perf_counter()
        try:
            loader()
        except Exception:
            logger.exception("warm-up: %s failed, so the app will not start", loader.__name__)
            raise
        logger.info("warm-up: %s ready in %.1fs", loader.__name__, time.perf_counter() - started)


async def close_clients() -> None:
    """Close each client on its own, so one failure does not leave the rest open."""
    for close in CLOSERS:
        try:
            await close()
        except Exception:
            logger.exception("shutdown: %s failed", close.__name__)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    if get_settings().warm_up_on_startup:
        # In a thread so the loop stays responsive (Ctrl+C) during a load of several seconds.
        await asyncio.to_thread(warm_up_models)
    else:
        logger.warning("Warm-up is off: the models load on the first request that needs them")
    yield
    await close_clients()
