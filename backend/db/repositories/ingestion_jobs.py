"""Every read and write of the `ingestion_jobs` table.

A job row is the audit trail for one ingest attempt: when it started, what it
produced, and — if it broke — what the error was. Separate from the document's
own `status` because a document has one current state but many attempts.
"""

import logging

from db.repositories import ERROR_MAX_CHARS, utc_now_iso
from db.session import get_supabase

logger = logging.getLogger(__name__)

TABLE = "ingestion_jobs"


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
