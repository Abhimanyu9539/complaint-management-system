"""Every read and write of the `dept_responses` table: what an escalated department answered."""

import logging

from cms.db.session import get_supabase

logger = logging.getLogger(__name__)

TABLE = "dept_responses"

DEPT_RESPONSE_COLUMNS = "id,ticket_id,department_id,answer_text,created_at"


async def insert_response(row: dict) -> dict:
    """Insert one department answer and return the created row."""
    try:
        response = await get_supabase().table(TABLE).insert(row).execute()
    except Exception:
        logger.exception("Failed to insert a %s row for ticket %s", TABLE, row.get("ticket_id"))
        raise

    if not response.data:
        raise RuntimeError("Department response insert returned no row")
    return response.data[0]


async def list_responses(ticket_id: str) -> list[dict]:
    """Every answer recorded for a ticket, newest first."""
    try:
        response = await (
            get_supabase()
            .table(TABLE)
            .select(DEPT_RESPONSE_COLUMNS)
            .eq("ticket_id", ticket_id)
            .order("created_at", desc=True)
            .execute()
        )
    except Exception:
        logger.exception("Failed to list %s rows for ticket %s", TABLE, ticket_id)
        raise
    return response.data or []
