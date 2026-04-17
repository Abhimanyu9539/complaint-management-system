"""Every read and write of the `tickets` table.

A ticket is one customer complaint and its lifecycle. The state machine that
governs which status may follow which lives in `services/ticket_service.py` —
this module moves rows and does not decide whether a move is legal.

`resolution_path` is the column the escalation-rate metric reads (lld.md:257).
It is null until the ticket is resolved, and that null is meaningful: it means
"not yet decided", not "direct". Every read here preserves it.
"""

import asyncio
import logging

from cms.db.repositories import utc_now_iso
from cms.db.session import get_supabase

logger = logging.getLogger(__name__)

TABLE = "tickets"

# The full row as every reader wants it. `body` and `source` arrive with
# migration 0017 — a deployment that has not applied it will get a PostgREST
# error naming the missing column, which is a better failure than silently
# dropping the complaint text.
TICKET_COLUMNS = (
    "id,ticket_no,status,severity,subject,body,source,customer_email,"
    "predicted_dept,dept_confidence,escalated_dept,category,resolution_path,"
    "created_at,updated_at,resolved_at"
)

TICKET_STATUSES: tuple[str, ...] = (
    "new",
    "processing",
    "drafted",
    "needs_review",
    "escalated",
    "dept_responded",
    "resolved",
    "processing_failed",
)

TICKET_SEVERITIES: tuple[str, ...] = ("low", "normal", "high", "critical")

# Escalated and awaiting a department. Distinct from a *resolved* escalation:
# these have no `resolution_path` yet, so they count towards the open backlog
# and not towards the escalation rate.
OPEN_ESCALATED_STATUSES: tuple[str, ...] = ("escalated", "dept_responded")

RESOLUTION_PATHS: tuple[str, ...] = ("direct", "escalated")


async def create_ticket(row: dict) -> dict:
    """Insert one ticket and return the created row.

    Returns the whole row rather than just the id, because `ticket_no` is
    `GENERATED ALWAYS AS IDENTITY` — the caller cannot know the customer's
    reference number without reading back what the database assigned.
    """
    try:
        response = await get_supabase().table(TABLE).insert(row).execute()
    except Exception:
        logger.exception("Failed to insert a %s row", TABLE)
        raise

    if not response.data:
        raise RuntimeError("Ticket insert returned no row")
    return response.data[0]


async def fetch_ticket(ticket_id: str) -> dict:
    """One ticket by id.

    Raises `LookupError` when it does not exist, matching `cases.fetch_case`, so
    the route layer can map a missing ticket to 404 without inspecting shapes.
    """
    try:
        response = await (
            get_supabase()
            .table(TABLE)
            .select(TICKET_COLUMNS)
            .eq("id", ticket_id)
            .limit(1)
            .execute()
        )
    except Exception:
        logger.exception("Failed to fetch %s row %s", TABLE, ticket_id)
        raise

    rows = response.data or []
    if not rows:
        raise LookupError(f"No ticket with id {ticket_id}")
    return rows[0]


async def update_ticket(ticket_id: str, patch: dict) -> dict:
    """Apply a partial update and return the updated row.

    No status validation here on purpose — `ticket_service.transition` owns the
    state machine, and duplicating the rules in the repository is how the two
    copies drift apart.
    """
    try:
        response = await get_supabase().table(TABLE).update(patch).eq("id", ticket_id).execute()
    except Exception:
        logger.exception("Failed to update %s row %s", TABLE, ticket_id)
        raise

    if not response.data:
        raise LookupError(f"No ticket with id {ticket_id}")
    return response.data[0]


async def mark_resolved(ticket_id: str, resolution_path: str) -> dict:
    """Close a ticket, stamping the path it took to get there.

    `resolved_at` is written here rather than by a trigger so that resolving is
    one round trip and the timestamp matches the row the caller gets back.
    """
    return await update_ticket(
        ticket_id,
        {
            "status": "resolved",
            "resolution_path": resolution_path,
            "resolved_at": utc_now_iso(),
        },
    )


# ---------------------------------------------------------------------------
# Reads for the admin surface
#
# Same rule as `ingestion_jobs`: log and re-raise. An escalation rate of zero
# because Supabase was unreachable looks exactly like a perfectly-performing
# system, which is the one reading this metric must never produce by accident.
# ---------------------------------------------------------------------------


async def list_tickets(
    *,
    status: str | None = None,
    severity: str | None = None,
    search: str | None = None,
    limit: int = 25,
    offset: int = 0,
) -> tuple[list[dict], int]:
    """A page of tickets, newest first, plus the exact unpaged total.

    `search` matches subject or customer email. Unlike `ingestion_jobs.list_jobs`
    both fields live on this table, so the filter is expressible here and the
    service layer does not have to resolve anything first.
    """
    try:
        query = get_supabase().table(TABLE).select(TICKET_COLUMNS, count="exact")

        if status:
            query = query.eq("status", status)
        if severity:
            query = query.eq("severity", severity)
        if search:
            # PostgREST `or` takes a comma-separated filter list. Commas inside
            # the pattern would split it into extra filters, so they are dropped
            # rather than escaped — a comma in a subject search is not worth a
            # quoting scheme that has to stay correct forever.
            pattern = f"%{search.replace(',', ' ')}%"
            query = query.or_(f"subject.ilike.{pattern},customer_email.ilike.{pattern}")

        response = await query.order("created_at", desc=True).range(offset, offset + limit - 1).execute()
    except Exception:
        logger.exception("Failed to list %s rows", TABLE)
        raise

    return response.data or [], response.count or 0


async def count_tickets_by_status() -> dict[str, int]:
    """How many tickets sit in each status — the funnel.

    One `count="exact", head=True` per status, for the reason spelled out in
    `ingestion_jobs.count_jobs_by_status`: a bare select caps at 1000 rows and
    would under-count silently. The eight probes are independent, so they go out
    as one wave rather than eight sequential round-trips.
    """

    async def count_one(status: str) -> int:
        response = await (
            get_supabase()
            .table(TABLE)
            .select("id", count="exact", head=True)
            .eq("status", status)
            .execute()
        )
        return response.count or 0

    try:
        counts = await asyncio.gather(*(count_one(s) for s in TICKET_STATUSES))
    except Exception:
        logger.exception("Failed to count %s rows by status", TABLE)
        raise
    return dict(zip(TICKET_STATUSES, counts, strict=True))


async def count_by_resolution_path() -> dict[str, int]:
    """Resolved tickets split by the path they took — the escalation numerator
    and denominator.

    Only rows with a non-null `resolution_path` are counted, which is exactly
    the set of resolved tickets. An escalated-but-still-open ticket has no path
    yet and must not be counted as either: it has not finished, and guessing
    would move the metric before the outcome is known.
    """

    async def count_one(path: str) -> int:
        response = await (
            get_supabase()
            .table(TABLE)
            .select("id", count="exact", head=True)
            .eq("resolution_path", path)
            .execute()
        )
        return response.count or 0

    try:
        counts = await asyncio.gather(*(count_one(p) for p in RESOLUTION_PATHS))
    except Exception:
        logger.exception("Failed to count %s rows by resolution path", TABLE)
        raise
    return dict(zip(RESOLUTION_PATHS, counts, strict=True))


async def count_open_escalated() -> int:
    """Tickets escalated to a department and still waiting on one."""
    try:
        response = await (
            get_supabase()
            .table(TABLE)
            .select("id", count="exact", head=True)
            .in_("status", list(OPEN_ESCALATED_STATUSES))
            .execute()
        )
    except Exception:
        logger.exception("Failed to count open escalated %s rows", TABLE)
        raise
    return response.count or 0


async def count_escalations_by_department() -> dict[str, int]:
    """Escalation counts keyed by `escalated_dept`.

    Reads the rows rather than issuing one count per department: the department
    set is closed at twelve, but the alternative is twelve round trips for a
    panel that already makes several. The 1000-row cap applies, so the cap is
    checked and logged — under-reporting escalations would flatter the metric,
    which is the direction that matters.
    """
    try:
        response = await (
            get_supabase()
            .table(TABLE)
            .select("escalated_dept")
            .not_.is_("escalated_dept", "null")
            .limit(5000)
            .execute()
        )
    except Exception:
        logger.exception("Failed to count %s escalations by department", TABLE)
        raise

    rows = response.data or []
    if len(rows) >= 5000:
        logger.warning(
            "count_escalations_by_department hit the 5000 row cap — "
            "the per-department breakdown is under-reporting"
        )

    counts: dict[str, int] = {}
    for row in rows:
        dept = row.get("escalated_dept")
        if dept:
            counts[dept] = counts.get(dept, 0) + 1
    return counts


async def list_tickets_since(since_iso: str, limit: int = 5000) -> list[dict]:
    """Every ticket created at or after `since_iso`, for the per-day charts.

    Same safety-valve reasoning as `ingestion_jobs.list_jobs_since`: the caller
    aggregates over the whole window, so a silent truncation would skew the
    chart rather than shorten it.
    """
    try:
        response = await (
            get_supabase()
            .table(TABLE)
            .select("id,status,resolution_path,created_at,resolved_at")
            .gte("created_at", since_iso)
            .order("created_at", desc=False)
            .limit(limit)
            .execute()
        )
    except Exception:
        logger.exception("Failed to list %s rows since %s", TABLE, since_iso)
        raise

    rows = response.data or []
    if len(rows) >= limit:
        logger.warning(
            "list_tickets_since hit the %d row cap — the summary for this window is truncated",
            limit,
        )
    return rows
