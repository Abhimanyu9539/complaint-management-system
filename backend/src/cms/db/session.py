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
