"""Reads of the `profiles` table: one row per Supabase user, with their role."""

import logging

from cms.db.session import get_supabase

logger = logging.getLogger(__name__)

TABLE = "profiles"

PROFILE_COLUMNS = "id,email,display_name,role,is_active"


async def fetch_profile(user_id: str) -> dict:
    """One profile by user id. Raises `LookupError` when it does not exist."""
    try:
        response = await (
            get_supabase()
            .table(TABLE)
            .select(PROFILE_COLUMNS)
            .eq("id", user_id)
            .limit(1)
            .execute()
        )
    except Exception:
        logger.exception("Failed to fetch %s row %s", TABLE, user_id)
        raise

    rows = response.data or []
    if not rows:
        raise LookupError(f"No profile with id {user_id}")
    return rows[0]
