"""Every read and write of the `policies` table.

Deliberately a near-mirror of `cases.py` rather than a shared parameterised
module: the two corpora differ in the columns that matter (`lifecycle` here,
`category` there) and are expected to keep diverging — policies gain review and
publication state, cases do not.
"""

import asyncio
import logging

from cms.db.repositories import ERROR_MAX_CHARS, utc_now_iso
from cms.db.session import get_supabase

logger = logging.getLogger(__name__)

TABLE = "policies"

# `lifecycle` takes the slot `category` occupies for cases: it is what lets
# retrieval restrict to published clauses.
POLICY_COLUMNS = "id,title,department_id,lifecycle,source,status,content_hash"


async def fetch_policy(policy_id: str) -> dict:
    """Read one policy row. Raises LookupError if the id does not exist."""
    response = await (
        get_supabase().table(TABLE).select(POLICY_COLUMNS).eq("id", policy_id).execute()
    )
    if not response.data:
        raise LookupError(f"No {TABLE} row with id {policy_id}")
    return response.data[0]


POLICY_REINGEST_COLUMNS = "source_ref,storage_path"


async def fetch_policy_for_reingest(policy_id: str) -> dict:
    """The fields needed to recover a policy's raw body for re-ingest.

    Policies have no body column (see the module docstring) — the text lives
    only in `policy_chunks` and in the source file, so `ingestion/reingest.py`
    reads `storage_path` (the primary route, via Supabase Storage) and
    `source_ref` (the on-disk seed-file fallback) instead. Raises LookupError
    if the id does not exist.
    """
    response = await (
        get_supabase()
        .table(TABLE)
        .select(POLICY_REINGEST_COLUMNS)
        .eq("id", policy_id)
        .execute()
    )
    if not response.data:
        raise LookupError(f"No {TABLE} row with id {policy_id}")
    return response.data[0]


async def upsert_policy(row: dict) -> str:
    """Insert or update a policy keyed by `source_ref`, returning its id.

    For the seed corpus `source_ref` is the source filename
    (`warranty-policy.md`), which is what makes re-seeding update the same rows.
    """
    response = await (
        get_supabase().table(TABLE).upsert(row, on_conflict="source_ref").execute()
    )
    return response.data[0]["id"]


async def mark_policy_processing(policy_id: str) -> None:
    """Claim the row before the work starts, clearing any previous error."""
    await get_supabase().table(TABLE).update({"status": "processing", "error": None}).eq(
        "id", policy_id
    ).execute()


async def mark_policy_indexed(policy_id: str, content_hash: str, chunk_count: int) -> None:
    """Record the successful ingest. Writing `content_hash` arms the short-circuit."""
    await get_supabase().table(TABLE).update(
        {
            "status": "indexed",
            "content_hash": content_hash,
            "chunk_count": chunk_count,
            "indexed_at": utc_now_iso(),
            "error": None,
        }
    ).eq("id", policy_id).execute()


async def mark_policy_failed(policy_id: str, error: str) -> None:
    await get_supabase().table(TABLE).update(
        {"status": "failed", "error": error[:ERROR_MAX_CHARS]}
    ).eq("id", policy_id).execute()


# ---------------------------------------------------------------------------
# Reads for the admin surface. Mirrors `cases.py` for the reasons in the module
# docstring: the two tables are expected to keep diverging, so a shared helper
# would have to grow a table parameter and then a column parameter.
#
# These log and re-raise rather than returning an empty result — a zero shown
# during an outage is indistinguishable from a genuinely empty corpus.
# ---------------------------------------------------------------------------

DOC_STATUSES: tuple[str, ...] = ("pending", "processing", "indexed", "failed", "deleting")


async def count_policies_by_status() -> dict[str, int]:
    """How many policies sit in each lifecycle state.

    `count="exact", head=True` per status rather than selecting and tallying:
    PostgREST caps a bare select at 1000 rows.

    The per-status probes are independent, so they run as one wave.
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
        counts = await asyncio.gather(*(count_one(s) for s in DOC_STATUSES))
    except Exception:
        logger.exception("Failed to count %s rows by status", TABLE)
        raise
    return dict(zip(DOC_STATUSES, counts, strict=True))


async def list_processing_policies(limit: int = 20) -> list[dict]:
    """Policies claimed for ingest that never finished — see `cases.py`."""
    try:
        response = await (
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


async def count_policies_with_storage() -> int:
    """Policies backed by a file in Supabase Storage.

    A count, not a byte total: measuring size would need a Storage list call
    per object, and the admin panel labels this "files stored" for that reason.
    """
    try:
        response = await (
            get_supabase()
            .table(TABLE)
            .select("id", count="exact", head=True)
            .not_.is_("storage_path", "null")
            .execute()
        )
    except Exception:
        logger.exception("Failed to count %s rows with a storage_path", TABLE)
        raise
    return response.count or 0


async def titles_for_ids(policy_ids: list[str]) -> dict[str, str]:
    """Map policy ids to titles, omitting ids that no longer exist.

    The `ingestion_jobs` table has no FK on `document_id`, so a job can outlive
    its document. A missing key means "deleted", not "error".
    """
    if not policy_ids:
        return {}
    try:
        response = await (
            get_supabase().table(TABLE).select("id,title").in_("id", policy_ids).execute()
        )
    except Exception:
        logger.exception("Failed to resolve %s titles", TABLE)
        raise
    return {row["id"]: row["title"] for row in response.data or []}


async def list_policy_options(limit: int = 200) -> list[dict]:
    """Id, title and status for the admin's single-document ingest picker."""
    try:
        response = await (
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


async def statuses_for_source_refs(source_refs: list[str]) -> dict[str, str]:
    """Map seed `source_ref`s (filenames) to their row status.

    A missing key means "never seeded" — the on-disk seed corpus is the full
    set the admin ingest picker shows, and Postgres holds only what has
    actually been registered. Logs and re-raises rather than degrading to an
    empty map: a status lookup failure would otherwise render every file as
    "not ingested", which is the exact false picture this function exists to
    prevent, and the trigger button next to a degraded list would fail anyway
    since it also needs Supabase.
    """
    if not source_refs:
        return {}
    try:
        response = await (
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
