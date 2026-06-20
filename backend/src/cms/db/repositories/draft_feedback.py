"""Every read and write of the `draft_feedback` table.

One row per draft, at most (`draft_id` is UNIQUE): what an agent did with it.
That uniqueness is also what stops one draft being sent twice.
"""

import logging

from cms.db.session import get_supabase

logger = logging.getLogger(__name__)

TABLE = "draft_feedback"

FEEDBACK_COLUMNS = "id,draft_id,user_id,action,final_text,edit_reason,created_at"


async def insert_feedback(row: dict) -> dict:
    """Insert one feedback row and return it. Fails if the draft already has one."""
    try:
        response = await get_supabase().table(TABLE).insert(row).execute()
    except Exception:
        logger.exception("Failed to insert a %s row for draft %s", TABLE, row.get("draft_id"))
        raise

    if not response.data:
        raise RuntimeError("Feedback insert returned no row")
    return response.data[0]


async def fetch_feedback(draft_id: str) -> dict | None:
    """The feedback on a draft, or None if nobody has acted on it yet."""
    try:
        response = await (
            get_supabase()
            .table(TABLE)
            .select(FEEDBACK_COLUMNS)
            .eq("draft_id", draft_id)
            .limit(1)
            .execute()
        )
    except Exception:
        logger.exception("Failed to fetch %s for draft %s", TABLE, draft_id)
        raise

    rows = response.data or []
    return rows[0] if rows else None


async def delete_feedback(feedback_id: str) -> None:
    """Remove a feedback row — only to undo a send whose email never left."""
    try:
        await get_supabase().table(TABLE).delete().eq("id", feedback_id).execute()
    except Exception:
        logger.exception("Failed to delete %s row %s", TABLE, feedback_id)
        raise
