"""Every read and write of the `agent_runs` table: one row per ticket-graph run."""

import logging

from cms.db.session import get_supabase

logger = logging.getLogger(__name__)

TABLE = "agent_runs"

RUN_COLUMNS = (
    "id,ticket_id,ticket_no,subject,trigger,status,outcome,review_reasons,"
    "predicted_dept,dept_confidence,category,grounded,regenerated,precedents_offered,"
    "steps,errors,latency_ms,started_at,finished_at"
)

# Why a run happened, and how it ended. Mirrors the CHECKs in migration 0025.
TRIGGERS: tuple[str, ...] = ("created", "dept_response", "regenerate", "cli")
RUN_STATUSES: tuple[str, ...] = ("succeeded", "no_match", "blocked", "failed")


async def insert_run(row: dict) -> None:
    """Record one run. Swallows its failure: the run log must never break ticket processing."""
    try:
        await get_supabase().table(TABLE).insert(row).execute()
    except Exception:
        logger.exception("Failed to record agent run %s for ticket %s", row.get("id"), row.get("ticket_id"))


async def list_runs(
    *,
    status: str | None = None,
    search: str | None = None,
    limit: int = 25,
    offset: int = 0,
) -> tuple[list[dict], int]:
    """A page of runs, newest first, plus the unpaged total.

    A numeric `search` matches the ticket number; anything else matches the subject.
    """
    try:
        query = get_supabase().table(TABLE).select(RUN_COLUMNS, count="exact")
        if status:
            query = query.eq("status", status)
        if search:
            term = search.strip().lstrip("#")
            if term.isdigit():
                query = query.eq("ticket_no", int(term))
            else:
                query = query.ilike("subject", f"%{term}%")

        response = await (
            query.order("started_at", desc=True).range(offset, offset + limit - 1).execute()
        )
    except Exception:
        logger.exception("Failed to list %s rows", TABLE)
        raise

    return response.data or [], response.count or 0


async def list_runs_since(since_iso: str, limit: int) -> list[dict]:
    """Every run started at or after `since_iso`, for the summary."""
    try:
        response = await (
            get_supabase()
            .table(TABLE)
            .select("status,outcome,latency_ms,steps")
            .gte("started_at", since_iso)
            .order("started_at", desc=False)
            .limit(limit)
            .execute()
        )
    except Exception:
        logger.exception("Failed to list %s rows since %s", TABLE, since_iso)
        raise

    rows = response.data or []
    if len(rows) >= limit:
        logger.warning("list_runs_since hit the %d row cap; the summary is truncated", limit)
    return rows
