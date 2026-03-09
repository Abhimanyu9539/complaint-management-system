"""The database handle, for backend-side writes.

This is the Supabase equivalent of a SQLAlchemy session factory: the one place
that knows how to open a connection, cached so the rest of the codebase asks for
a client instead of constructing one.

Uses the **service role** key, which bypasses RLS. That is deliberate and
necessary here: the ingestion pipeline writes chunk rows on behalf of the whole
org (build.md §0.5, shared KB per D2), so it cannot run under a single user's
policies. The flip side is that this key must never reach a browser — the API
layer uses the publishable key + a verified JWT for user-scoped reads.
"""

import logging
from functools import lru_cache

from cms.config.settings import get_settings
from supabase import Client, create_client

logger = logging.getLogger(__name__)


@lru_cache
def get_supabase() -> Client:
    """Service-role Supabase client, constructed once per process."""
    settings = get_settings()
    try:
        client = create_client(settings.supabase_url, settings.supabase_secret_key)
    except Exception:
        logger.exception(
            "Failed to construct Supabase client for %s", settings.supabase_url
        )
        raise
    logger.debug("Supabase client constructed for %s", settings.supabase_url)
    return client
