"""Every read and write of the `policies` table.

Deliberately a near-mirror of `cases.py` rather than a shared parameterised
module: the two corpora differ in the columns that matter (`lifecycle` here,
`category` there) and are expected to keep diverging — policies gain review and
publication state, cases do not.
"""

import logging

from db.repositories import ERROR_MAX_CHARS, utc_now_iso
from db.session import get_supabase

logger = logging.getLogger(__name__)

TABLE = "policies"

# `lifecycle` takes the slot `category` occupies for cases: it is what lets
# retrieval restrict to published clauses.
POLICY_COLUMNS = "id,title,department_id,lifecycle,source,status,content_hash"


def fetch_policy(policy_id: str) -> dict:
    """Read one policy row. Raises LookupError if the id does not exist."""
    response = (
        get_supabase().table(TABLE).select(POLICY_COLUMNS).eq("id", policy_id).execute()
    )
    if not response.data:
        raise LookupError(f"No {TABLE} row with id {policy_id}")
    return response.data[0]


def upsert_policy(row: dict) -> str:
    """Insert or update a policy keyed by `source_ref`, returning its id.

    For the seed corpus `source_ref` is the source filename
    (`warranty-policy.md`), which is what makes re-seeding update the same rows.
    """
    response = (
        get_supabase().table(TABLE).upsert(row, on_conflict="source_ref").execute()
    )
    return response.data[0]["id"]


def mark_policy_processing(policy_id: str) -> None:
    """Claim the row before the work starts, clearing any previous error."""
    get_supabase().table(TABLE).update({"status": "processing", "error": None}).eq(
        "id", policy_id
    ).execute()


def mark_policy_indexed(policy_id: str, content_hash: str, chunk_count: int) -> None:
    """Record the successful ingest. Writing `content_hash` arms the short-circuit."""
    get_supabase().table(TABLE).update(
        {
            "status": "indexed",
            "content_hash": content_hash,
            "chunk_count": chunk_count,
            "indexed_at": utc_now_iso(),
            "error": None,
        }
    ).eq("id", policy_id).execute()


def mark_policy_failed(policy_id: str, error: str) -> None:
    get_supabase().table(TABLE).update(
        {"status": "failed", "error": error[:ERROR_MAX_CHARS]}
    ).eq("id", policy_id).execute()
