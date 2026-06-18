"""Every read and write of the `drafts` table.

A draft is one generated reply for a ticket, versioned per ticket and kind. Rows
are only ever added: a re-run writes the next version, and the history of what
the model wrote stays for failure attribution.
"""

import logging

from cms.db.session import get_supabase

logger = logging.getLogger(__name__)

TABLE = "drafts"

# `grounded` and `guard_reasons` arrive with migration 0021.
DRAFT_COLUMNS = (
    "id,ticket_id,version,kind,draft_text,retrieved_cases,policy_refs,no_match,"
    "grounded,guard_reasons,model,prompt_version,langsmith_run_id,created_at"
)

CUSTOMER_REPLY = "customer_reply"


async def insert_draft(row: dict) -> dict:
    """Insert one draft and return the created row."""
    try:
        response = await get_supabase().table(TABLE).insert(row).execute()
    except Exception:
        logger.exception("Failed to insert a %s row for ticket %s", TABLE, row.get("ticket_id"))
        raise

    if not response.data:
        raise RuntimeError("Draft insert returned no row")
    return response.data[0]


async def fetch_latest_draft(ticket_id: str, kind: str = CUSTOMER_REPLY) -> dict | None:
    """The newest draft of `kind` for a ticket, or None if it has none."""
    try:
        response = await (
            get_supabase()
            .table(TABLE)
            .select(DRAFT_COLUMNS)
            .eq("ticket_id", ticket_id)
            .eq("kind", kind)
            .order("version", desc=True)
            .limit(1)
            .execute()
        )
    except Exception:
        logger.exception("Failed to fetch the latest %s draft for ticket %s", kind, ticket_id)
        raise

    rows = response.data or []
    return rows[0] if rows else None
