"""Every read and write of the `inbound_emails` table: one row per email n8n posted."""

import logging

from postgrest.exceptions import APIError

from cms.db.session import get_supabase

logger = logging.getLogger(__name__)

TABLE = "inbound_emails"

# Postgres unique_violation: this `message_id` is already recorded.
UNIQUE_VIOLATION = "23505"


async def claim_email(row: dict) -> str | None:
    """Insert the email as `received` and return its id. None when it was already recorded."""
    try:
        response = await get_supabase().table(TABLE).insert({**row, "outcome": "received"}).execute()
    except APIError as exc:
        if exc.code == UNIQUE_VIOLATION:
            logger.info("Email %s was already received", row.get("message_id"))
            return None
        logger.exception("Failed to insert a %s row", TABLE)
        raise
    except Exception:
        logger.exception("Failed to insert a %s row", TABLE)
        raise

    if not response.data:
        raise RuntimeError("Inbound email insert returned no row")
    return response.data[0]["id"]


async def finish_email(
    email_id: str, outcome: str, reason: str | None = None, ticket_id: str | None = None
) -> None:
    """Record what the email became."""
    try:
        await (
            get_supabase()
            .table(TABLE)
            .update({"outcome": outcome, "reason": reason, "ticket_id": ticket_id})
            .eq("id", email_id)
            .execute()
        )
    except Exception:
        logger.exception("Failed to update %s row %s", TABLE, email_id)
        raise
