"""Composes Extract → Transform → Load: one case or policy in, chunks + points out.

Cases and policies are separate corpora — separate tables, separate chunk
tables, separate Qdrant collections — so ingestion has two entry points,
`ingest_case` and `ingest_policy`, rather than one function dispatching on a
type string. They are not merged because the corpora genuinely differ (chunking
strategy, payload fields, write permissions); they share a module because the
crash-safety protocol below must not drift between two independent copies.

This module owns only orchestration. The steps live in the packages named after
them — `extract/`, `transform/`, `load/` — and every table write goes through
`db.repositories`, so what remains here is the *order*, which is the part that
matters.

The write order both entry points follow is the consistency protocol from
build.md §0.5 and is not arbitrary:

    chunk → write chunk rows → embed + upsert Qdrant points → mark indexed

Postgres before Qdrant, because Postgres is the source of truth and Qdrant is a
rebuildable cache of it. A crash in between leaves the parent row visibly stuck
at `status='processing'` and a re-run finishes the job. The reverse order would
leave Qdrant points that retrieval can find but Postgres cannot explain — ghost
chunks are the dangerous failure direction.

Idempotency has three layers, so re-running a seed or a retry is free and safe:
  1. ingest-key short-circuit — unchanged documents cost zero OpenAI calls, and
     a changed chunking or embedding recipe re-ingests instead of skipping;
  2. chunk-table upsert on `(fk_column, chunk_index)` — rows update in place;
  3. deterministic Qdrant point ids — points overwrite instead of duplicating.
"""

import logging
from collections.abc import Awaitable, Callable
from dataclasses import dataclass

from langsmith import traceable

from cms.config.settings import get_settings
from cms.db.repositories.cases import (
    fetch_case,
    mark_case_failed,
    mark_case_indexed,
    mark_case_processing,
)
from cms.db.repositories.ingestion_jobs import (
    claim_job,
    fail_job,
    finish_job,
    start_job,
)
from cms.db.repositories.policies import (
    fetch_policy,
    mark_policy_failed,
    mark_policy_indexed,
    mark_policy_processing,
)
from cms.ingestion.load.doc_store_loader import write_chunks
from cms.ingestion.load.vector_loader import (
    delete_stale_points,
    existing_point_ids,
    upsert_points,
)
from cms.ingestion.transform.chunker import chunk_case, chunk_policy
from cms.ingestion.transform.cleaner import compute_ingest_key
from cms.ingestion.transform.enricher import case_metadata, policy_metadata

logger = logging.getLogger(__name__)

# Ingest traces go to their own LangSmith project (build.md §0.3.3) so they do
# not bury the chat traces we actually read day to day.
INGEST_PROJECT = f"{get_settings().langsmith_project}-ingest"


@dataclass
class IngestResult:
    """Outcome of one document ingest, for the caller's summary line."""

    document_id: str
    status: str  # "indexed" | "skipped"
    chunk_count: int
    point_count: int


async def _record_failure(
    mark_document_failed: Callable[[str, str], Awaitable[None]],
    document_id: str,
    job_id: str | None,
    error: str,
) -> None:
    """Record the failure on both the document row and the job row.

    Wrapped separately: if Postgres is what broke, this bookkeeping fails too,
    and it must not replace the original exception with a confusing second one.
    """
    try:
        await mark_document_failed(document_id, error)
        if job_id:
            await fail_job(job_id, error)
    except Exception:
        logger.exception("Could not record failure state for document %s", document_id)


@traceable(name="ingest_case", project_name=INGEST_PROJECT)
async def ingest_case(
    case_id: str, raw_text: str, *, force: bool = False, job_id: str | None = None
) -> IngestResult:
    """Ingest one case end to end. Returns what happened; raises on failure.

    `force` bypasses the ingest-key short-circuit — the admin trigger's
    checkbox, and the override for a strategy change no recipe can catch.
    `job_id`, when given, is an already-`queued` row from
    `ingestion_jobs.queue_job` that this call claims instead of inserting a
    fresh one: the HTTP trigger path needs a job id to hand back before this
    function is even called. `cms-seed` never passes one and keeps the
    original insert-on-start behaviour unchanged.
    """
    settings = get_settings()
    collection = settings.qdrant_cases_collection

    case = await fetch_case(case_id)
    ingest_key = compute_ingest_key(raw_text, settings.case_recipe)

    if not force and case["status"] == "indexed" and case["ingest_key"] == ingest_key:
        logger.info(
            "Case %s ('%s') unchanged — skipping (no embedding cost)",
            case_id,
            case["title"],
        )
        if job_id:
            await finish_job(job_id, 0, 0)
        return IngestResult(case_id, "skipped", 0, 0)

    try:
        if job_id:
            await claim_job(job_id)
        else:
            job_id = await start_job("case", case_id)
        await mark_case_processing(case_id)

        chunk_texts = chunk_case(raw_text)
        chunk_rows = await write_chunks("case_chunks", "case_id", case_id, chunk_texts)

        # Snapshot before writing, so the diff afterwards is exactly the points
        # the previous version left behind.
        previous_point_ids = await existing_point_ids(collection, case_id)
        point_ids = await upsert_points(
            collection, case_id, chunk_rows, case_metadata(case)
        )
        await delete_stale_points(collection, case_id, previous_point_ids - set(point_ids))

        await mark_case_indexed(case_id, ingest_key, len(chunk_rows))
        await finish_job(job_id, len(chunk_rows), len(point_ids))

    except Exception as exc:
        logger.exception("Ingest failed for case %s ('%s')", case_id, case["title"])
        await _record_failure(
            mark_case_failed, case_id, job_id, f"{type(exc).__name__}: {exc}"
        )
        raise

    logger.info(
        "Indexed case '%s': %d chunk(s), %d point(s)",
        case["title"],
        len(chunk_rows),
        len(point_ids),
    )
    return IngestResult(case_id, "indexed", len(chunk_rows), len(point_ids))


@traceable(name="ingest_policy", project_name=INGEST_PROJECT)
async def ingest_policy(
    policy_id: str, raw_text: str, *, force: bool = False, job_id: str | None = None
) -> IngestResult:
    """Ingest one policy end to end. Returns what happened; raises on failure.

    See `ingest_case` for what `force` and `job_id` are for — the two entry
    points share the same contract.
    """
    settings = get_settings()
    collection = settings.qdrant_policies_collection

    policy = await fetch_policy(policy_id)
    ingest_key = compute_ingest_key(raw_text, settings.policy_recipe)

    if not force and policy["status"] == "indexed" and policy["ingest_key"] == ingest_key:
        logger.info(
            "Policy %s ('%s') unchanged — skipping (no embedding cost)",
            policy_id,
            policy["title"],
        )
        if job_id:
            await finish_job(job_id, 0, 0)
        return IngestResult(policy_id, "skipped", 0, 0)

    try:
        if job_id:
            await claim_job(job_id)
        else:
            job_id = await start_job("policy", policy_id)
        await mark_policy_processing(policy_id)

        chunk_texts = chunk_policy(raw_text)
        chunk_rows = await write_chunks("policy_chunks", "policy_id", policy_id, chunk_texts)

        previous_point_ids = await existing_point_ids(collection, policy_id)
        point_ids = await upsert_points(
            collection, policy_id, chunk_rows, policy_metadata(policy)
        )
        await delete_stale_points(
            collection, policy_id, previous_point_ids - set(point_ids)
        )

        await mark_policy_indexed(policy_id, ingest_key, len(chunk_rows))
        await finish_job(job_id, len(chunk_rows), len(point_ids))

    except Exception as exc:
        logger.exception(
            "Ingest failed for policy %s ('%s')", policy_id, policy["title"]
        )
        await _record_failure(
            mark_policy_failed, policy_id, job_id, f"{type(exc).__name__}: {exc}"
        )
        raise

    logger.info(
        "Indexed policy '%s': %d chunk(s), %d point(s)",
        policy["title"],
        len(chunk_rows),
        len(point_ids),
    )
    return IngestResult(policy_id, "indexed", len(chunk_rows), len(point_ids))
