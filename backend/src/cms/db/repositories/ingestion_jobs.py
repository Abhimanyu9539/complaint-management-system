"""Every read and write of the `ingestion_jobs` table.

A job row is the audit trail for one ingest attempt: when it started, what it
produced, and — if it broke — what the error was. Separate from the document's
own `status` because a document has one current state but many attempts.
"""

import logging

from cms.db.repositories import ERROR_MAX_CHARS, utc_now_iso
from cms.db.session import get_supabase

logger = logging.getLogger(__name__)

TABLE = "ingestion_jobs"

# The full row, for the admin surface. Kept separate from the write helpers
# above because reads need every column and writes need none of them.
JOB_COLUMNS = (
    "id,doc_type,document_id,status,error,chunk_count,point_count,"
    "langsmith_run_id,created_at,started_at,finished_at"
)

JOB_STATUSES: tuple[str, ...] = ("queued", "running", "done", "failed")

# Statuses that mean "still in flight" — the dashboard's live queue.
ACTIVE_STATUSES: tuple[str, ...] = ("queued", "running")


def start_job(doc_type: str, document_id: str) -> str:
    """Open a running job row and return its id."""
    response = (
        get_supabase()
        .table(TABLE)
        .insert(
            {
                "doc_type": doc_type,
                "document_id": document_id,
                "status": "running",
                "started_at": utc_now_iso(),
            }
        )
        .execute()
    )
    return response.data[0]["id"]


def finish_job(job_id: str, chunk_count: int, point_count: int) -> None:
    get_supabase().table(TABLE).update(
        {
            "status": "done",
            "chunk_count": chunk_count,
            "point_count": point_count,
            "finished_at": utc_now_iso(),
        }
    ).eq("id", job_id).execute()


def fail_job(job_id: str, error: str) -> None:
    get_supabase().table(TABLE).update(
        {
            "status": "failed",
            "error": error[:ERROR_MAX_CHARS],
            "finished_at": utc_now_iso(),
        }
    ).eq("id", job_id).execute()


# ---------------------------------------------------------------------------
# Reads for the admin surface
#
# These log and re-raise rather than returning an empty result. A dashboard that
# renders zeros during an outage is indistinguishable from one reporting an idle
# system, and the operator has no way to tell which they are looking at.
# ---------------------------------------------------------------------------


def count_jobs_by_status() -> dict[str, int]:
    """How many jobs sit in each status.

    One `count="exact", head=True` request per status — four tiny round trips
    that transfer no rows. Deliberately not `select("status")` plus a Counter:
    PostgREST caps a bare select at 1000 rows, so that version would silently
    under-count the moment the append-only ops log outgrew a demo, and
    under-counting a *failure* metric is the worst way for this to break.
    """
    counts: dict[str, int] = {}
    try:
        for status in JOB_STATUSES:
            response = (
                get_supabase()
                .table(TABLE)
                .select("id", count="exact", head=True)
                .eq("status", status)
                .execute()
            )
            counts[status] = response.count or 0
    except Exception:
        logger.exception("Failed to count %s rows by status", TABLE)
        raise
    return counts


def list_jobs(
    *,
    status: str | None = None,
    doc_type: str | None = None,
    search: str | None = None,
    limit: int = 25,
    offset: int = 0,
) -> tuple[list[dict], int]:
    """A page of jobs, newest first, plus the exact unpaged total.

    `count="exact"` combined with `.range()` returns both in one request —
    PostgREST puts the full count in the Content-Range header, so the pager does
    not cost a second query.

    `search` matches the document id only. Titles live in `cases`/`policies` and
    this table has no join to them, so title search would mean resolving ids
    first; the service layer does that where it has both halves.
    """
    try:
        query = get_supabase().table(TABLE).select(JOB_COLUMNS, count="exact")

        if status:
            query = query.eq("status", status)
        if doc_type:
            query = query.eq("doc_type", doc_type)
        if search:
            query = query.ilike("document_id", f"%{search}%")

        response = (
            query.order("created_at", desc=True).range(offset, offset + limit - 1).execute()
        )
    except Exception:
        logger.exception("Failed to list %s rows", TABLE)
        raise

    return response.data or [], response.count or 0


def list_active_jobs(limit: int = 20) -> list[dict]:
    """Queued and running jobs, oldest first — what the queue panel renders.

    Oldest first on purpose: the job that has been waiting longest is the one an
    operator needs to see, and newest-first would bury it under fresh arrivals.
    """
    try:
        response = (
            get_supabase()
            .table(TABLE)
            .select(JOB_COLUMNS)
            .in_("status", list(ACTIVE_STATUSES))
            .order("created_at", desc=False)
            .limit(limit)
            .execute()
        )
    except Exception:
        logger.exception("Failed to list active %s rows", TABLE)
        raise
    return response.data or []


def list_jobs_since(since_iso: str, limit: int = 5000) -> list[dict]:
    """Every job created at or after `since_iso`, for the per-day charts.

    The limit is a safety valve, not a page: the summary endpoint aggregates
    over the whole window, so silently truncating would skew the chart. It is
    set well above any plausible window and logged if it is ever reached.
    """
    try:
        response = (
            get_supabase()
            .table(TABLE)
            .select(JOB_COLUMNS)
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
            "list_jobs_since hit the %d row cap — the summary for this window is truncated",
            limit,
        )
    return rows


def latest_finished_at() -> str | None:
    """When the most recent job finished, or None if none ever has."""
    try:
        response = (
            get_supabase()
            .table(TABLE)
            .select("finished_at")
            .not_.is_("finished_at", "null")
            .order("finished_at", desc=True)
            .limit(1)
            .execute()
        )
    except Exception:
        logger.exception("Failed to read the latest finished %s row", TABLE)
        raise

    rows = response.data or []
    return rows[0]["finished_at"] if rows else None
