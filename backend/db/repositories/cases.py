"""Every read and write of the `cases` table."""

import logging

from db.repositories import ERROR_MAX_CHARS, utc_now_iso
from db.session import get_supabase

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
