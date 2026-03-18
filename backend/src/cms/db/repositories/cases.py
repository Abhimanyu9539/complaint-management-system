"""Every read and write of the `cases` table."""

import logging

from cms.db.repositories import ERROR_MAX_CHARS, utc_now_iso
from cms.db.session import get_supabase

logger = logging.getLogger(__name__)

TABLE = "cases"

# Exactly the columns ingestion needs: the short-circuit check reads `status`
# and `content_hash`, the payload builder reads the rest.
CASE_COLUMNS = "id,title,department_id,category,source,status,content_hash"


def fetch_case(case_id: str) -> dict:
    """Read one case row. Raises LookupError if the id does not exist."""
    response = (
        get_supabase().table(TABLE).select(CASE_COLUMNS).eq("id", case_id).execute()
    )
    if not response.data:
        raise LookupError(f"No {TABLE} row with id {case_id}")
    return response.data[0]


CASE_REINGEST_COLUMNS = "complaint_text,dept_guidance,resolution_text"


def fetch_case_for_reingest(case_id: str) -> dict:
    """The fields `build_case_text` needs to rebuild a case's raw embedded text.

    Separate from `fetch_case`/`CASE_COLUMNS` — cases are self-contained in
    Postgres, so re-ingesting one over HTTP (`ingestion/reingest.py`) reads
    this instead of re-deriving text a document loader has to hand for free.
    Raises LookupError if the id does not exist.
    """
    response = (
        get_supabase()
        .table(TABLE)
        .select(CASE_REINGEST_COLUMNS)
        .eq("id", case_id)
        .execute()
    )
    if not response.data:
        raise LookupError(f"No {TABLE} row with id {case_id}")
    return response.data[0]


def upsert_case(row: dict) -> str:
    """Insert or update a case keyed by `source_ref`, returning its id.

    `source_ref` is what makes re-registering a corpus idempotent without
    deriving synthetic ids — for the seed corpus it is the case id (`C-1001`).
    """
    response = (
        get_supabase().table(TABLE).upsert(row, on_conflict="source_ref").execute()
    )
    return response.data[0]["id"]


def mark_case_processing(case_id: str) -> None:
    """Claim the row before the work starts, clearing any previous error.

    A crash from here on leaves the row visibly stuck at `processing`, which is
    what makes an interrupted ingest recoverable by re-running it.
    """
    get_supabase().table(TABLE).update({"status": "processing", "error": None}).eq(
        "id", case_id
    ).execute()


def mark_case_indexed(case_id: str, content_hash: str, chunk_count: int) -> None:
    """Record the successful ingest. Writing `content_hash` arms the short-circuit."""
    get_supabase().table(TABLE).update(
        {
            "status": "indexed",
            "content_hash": content_hash,
            "chunk_count": chunk_count,
            "indexed_at": utc_now_iso(),
            "error": None,
        }
    ).eq("id", case_id).execute()


def mark_case_failed(case_id: str, error: str) -> None:
    get_supabase().table(TABLE).update(
        {"status": "failed", "error": error[:ERROR_MAX_CHARS]}
    ).eq("id", case_id).execute()


# ---------------------------------------------------------------------------
# Reads for the admin surface
#
# These log and re-raise rather than swallowing into an empty result: a zero
# shown during an outage is indistinguishable from a genuinely empty corpus.
# ---------------------------------------------------------------------------

DOC_STATUSES: tuple[str, ...] = ("pending", "processing", "indexed", "failed", "deleting")


def count_cases_by_status() -> dict[str, int]:
    """How many cases sit in each lifecycle state.

    Uses `count="exact", head=True` per status rather than selecting the column
    and tallying — PostgREST caps a bare select at 1000 rows, which would
    silently under-report once the corpus grows past a demo.
    """
    counts: dict[str, int] = {}
    try:
        for status in DOC_STATUSES:
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


def list_processing_cases(limit: int = 20) -> list[dict]:
    """Cases claimed for ingest that never finished.

    `mark_case_processing` claims the row before the work begins, so anything
    still sitting here is the visible residue of a crashed run. That is the
    documented recovery signal, and nothing else surfaces it.
    """
    try:
        response = (
            get_supabase()
            .table(TABLE)
            .select("id,title,status,updated_at")
            .eq("status", "processing")
            .order("updated_at", desc=False)
            .limit(limit)
            .execute()
        )
    except Exception:
        logger.exception("Failed to list processing %s rows", TABLE)
        raise
    return response.data or []


def count_cases_by_department() -> dict[str, int]:
    """Indexed cases per department, for the distribution chart.

    Only indexed rows are counted: a pending or failed case is not in the
    retrieval corpus, so including it would overstate what the agent can
    actually reach.
    """
    try:
        response = (
            get_supabase()
            .table(TABLE)
            .select("department_id")
            .eq("status", "indexed")
            .limit(5000)
            .execute()
        )
    except Exception:
        logger.exception("Failed to count %s rows by department", TABLE)
        raise

    counts: dict[str, int] = {}
    for row in response.data or []:
        department = row.get("department_id")
        if department:
            counts[department] = counts.get(department, 0) + 1
    return counts


def titles_for_ids(case_ids: list[str]) -> dict[str, str]:
    """Map case ids to titles, omitting ids that no longer exist.

    This is the LEFT JOIN that `ingestion_jobs` cannot express in SQL: that
    table has no FK on `document_id` by design, so a job row outlives the
    document it describes. Callers must treat a missing key as "deleted" rather
    than as an error.
    """
    if not case_ids:
        return {}
    try:
        response = (
            get_supabase().table(TABLE).select("id,title").in_("id", case_ids).execute()
        )
    except Exception:
        logger.exception("Failed to resolve %s titles", TABLE)
        raise
    return {row["id"]: row["title"] for row in response.data or []}


def list_case_options(limit: int = 200) -> list[dict]:
    """Id, title and status for the admin's single-document ingest picker."""
    try:
        response = (
            get_supabase()
            .table(TABLE)
            .select("id,title,status")
            .order("title", desc=False)
            .limit(limit)
            .execute()
        )
    except Exception:
        logger.exception("Failed to list %s options", TABLE)
        raise
    return response.data or []


def statuses_for_source_refs(source_refs: list[str]) -> dict[str, str]:
    """Map seed `source_ref`s (case ids) to their row status.

    A missing key means "never seeded" — the on-disk seed corpus is the full
    set the admin ingest picker shows, and Postgres holds only what has
    actually been registered. Logs and re-raises rather than degrading to an
    empty map: see `policies.statuses_for_source_refs`, this is its mirror.
    """
    if not source_refs:
        return {}
    try:
        response = (
            get_supabase()
            .table(TABLE)
            .select("source_ref,status")
            .in_("source_ref", source_refs)
            .execute()
        )
    except Exception:
        logger.exception("Failed to resolve %s statuses by source_ref", TABLE)
        raise
    return {row["source_ref"]: row["status"] for row in response.data or []}


def count_by_resolution_path() -> dict[str, int]:
    """Resolved cases split by the path that resolved them.

    The second home of the escalation signal. `tickets.resolution_path` records
    it for live tickets; this records it for the resolved complaints already in
    the retrieval corpus, and the two must not be summed — a case may have been
    minted from a ticket, and a seeded case was never a ticket at all.

    Reported separately by the escalation metric for exactly that reason.
    """
    counts: dict[str, int] = {}
    try:
        for path in ("direct", "escalated"):
            response = (
                get_supabase()
                .table(TABLE)
                .select("id", count="exact", head=True)
                .eq("resolution_path", path)
                .execute()
            )
            counts[path] = response.count or 0
    except Exception:
        logger.exception("Failed to count %s rows by resolution path", TABLE)
        raise
    return counts
