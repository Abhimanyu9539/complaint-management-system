"""The service-role Supabase client. It bypasses RLS, so it must stay server-side.

It binds to the first event loop that uses it: never add a second `asyncio.run` to a process.
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


async def close_supabase() -> None:
    """Close the client's connection pools, if it was built.

    supabase-py has no `close()`, so the PostgREST and Storage sub-clients, the
    only ones this app uses, are closed directly.
    """
    if get_supabase.cache_info().currsize == 0:
        return
    client = get_supabase()
    for sub_client in (client._postgrest, client._storage):
        if sub_client is not None:
            await sub_client.session.aclose()
    logger.info("Supabase client closed")
