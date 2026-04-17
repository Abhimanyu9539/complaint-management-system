"""The database handle, for backend-side writes.

This is the Supabase equivalent of a SQLAlchemy session factory: the one place
that knows how to open a connection, cached so the rest of the codebase asks for
a client instead of constructing one.

Uses the **service role** key, which bypasses RLS. That is deliberate and
necessary here: the ingestion pipeline writes chunk rows on behalf of the whole
org (build.md §0.5, shared KB per D2), so it cannot run under a single user's
policies. The flip side is that this key must never reach a browser — the API
layer uses the publishable key + a verified JWT for user-scoped reads.

The client is async: every repository awaits `.execute()`. `AsyncClient` binds
its httpx connection pool to the event loop that first uses it, so a process
must drive it from one loop only — uvicorn has one, and each CLI does exactly
one `asyncio.run`. Never add a second `asyncio.run` to a process.
"""

import logging
from functools import lru_cache

from cms.config.settings import get_settings
from supabase import AsyncClient

logger = logging.getLogger(__name__)


@lru_cache
def get_supabase() -> AsyncClient:
    """Service-role Supabase client, constructed once per process.

    Constructed directly rather than via `create_async_client`, which is a
    coroutine and would make this factory unawaitable-cacheable. The only thing
    that helper adds is an end-user auth-session lookup used to set an
    `Authorization` header — meaningless for a service-role key, which carries
    its own. `.postgrest` and `.storage` are lazy properties, so nothing here
    opens a connection: that happens on the first awaited call.
    """
    settings = get_settings()
    try:
        client = AsyncClient(settings.supabase_url, settings.supabase_secret_key)
    except Exception:
        logger.exception(
            "Failed to construct Supabase client for %s", settings.supabase_url
        )
        raise
    logger.debug("Supabase client constructed for %s", settings.supabase_url)
    return client
