"""Assembles the admin panel's read models from the repositories.

This module exists so the route handlers stay four lines each and so the
"nothing above `db/repositories` names a column" rule survives contact with an
endpoint that has to join three tables.

How that rule is honoured here: repositories return raw dicts (the existing
precedent — `ingestion/pipeline.py` already reads `case["status"]`), and the
private `_to_*` adapters below are the *only* place those dict keys are read.
They immediately produce Pydantic models, so nothing downstream of an adapter
ever touches a string key. Filtering, ordering and pagination are expressed as
repository *arguments*, never as `.eq()` / `.order()` calls in this file.
"""

import logging
from datetime import UTC, datetime, timedelta

from cms.config.settings import get_settings
from cms.db.repositories import (
    cases,
    chunks,
    departments,
    ingestion_jobs,
    policies,
    tickets,
)
from cms.retrieval.vector_store import qdrant_store
from cms.schemas.admin import (
    ChunkRowCounts,
    CollectionStorage,
    CorpusResolutionSplit,
    DailyJobCount,
    DepartmentCount,
    DepartmentOption,
    DocumentCounts,
    DocumentCountsByType,
    DocumentOption,
    DurationStats,
    EscalationByDepartment,
    EscalationSummaryResponse,
    IngestionSummaryResponse,
    JobPage,
    JobSummary,
    OverviewResponse,
    QueueSnapshot,
    StorageResponse,
    StuckDocument,
)

logger = logging.getLogger(__name__)

# float32 per dimension. Qdrant stores dense vectors as f32 by default; this is
# the multiplier behind every "est." byte figure the panel shows.
BYTES_PER_DIMENSION = 4


# ---------------------------------------------------------------------------
# Adapters — the boundary where raw rows become typed values
# ---------------------------------------------------------------------------


def _duration_ms(row: dict) -> int | None:
    """finished_at − started_at in milliseconds, or None if either is missing.

    A job can carry `finished_at` without `started_at` if it failed before being
    claimed, so both are checked rather than assuming the pair.
    """
    started, finished = row.get("started_at"), row.get("finished_at")
    if not started or not finished:
        return None
    try:
        delta = _parse_iso(finished) - _parse_iso(started)
    except (TypeError, ValueError):
        logger.warning("Unparseable job timestamps on job %s", row.get("id"))
        return None
    milliseconds = int(delta.total_seconds() * 1000)
    return milliseconds if milliseconds >= 0 else None


def _parse_iso(value: str) -> datetime:
    """Parse a Postgres `timestamptz`, whether it ends in `Z` or an offset.

    `fromisoformat` has handled the `Z` suffix since 3.11, and this project
    pins 3.13, so no pre-normalisation is needed.
    """
    return datetime.fromisoformat(value)


def _to_job_summary(row: dict, titles: dict[str, str]) -> JobSummary:
    return JobSummary(
        id=row["id"],
        doc_type=row["doc_type"],
        document_id=row["document_id"],
        # Absent from the mapping means the document is gone. That is expected,
        # not an error — see the JobSummary field description.
        document_title=titles.get(row["document_id"]),
        status=row["status"],
        error=row.get("error"),
        chunk_count=row.get("chunk_count") or 0,
        point_count=row.get("point_count") or 0,
        langsmith_run_id=row.get("langsmith_run_id"),
        created_at=row["created_at"],
        started_at=row.get("started_at"),
        finished_at=row.get("finished_at"),
        duration_ms=_duration_ms(row),
    )


def _to_stuck_document(row: dict, doc_type: str) -> StuckDocument:
    return StuckDocument(
        id=row["id"],
        doc_type=doc_type,
        title=row.get("title") or row["id"],
        status=row["status"],
        since=row.get("updated_at") or "",
    )


def _resolve_titles(rows: list[dict]) -> dict[str, str]:
    """Look up document titles for a batch of job rows, both corpora at once.

    Two queries rather than one per row, and split by `doc_type` because the ids
    live in different tables — `ingestion_jobs.document_id` points at `cases` or
    `policies` depending on the row, which is exactly what Postgres cannot
    express as a foreign key.
    """
    case_ids = [row["document_id"] for row in rows if row["doc_type"] == "case"]
    policy_ids = [row["document_id"] for row in rows if row["doc_type"] == "policy"]

    titles: dict[str, str] = {}
    titles.update(cases.titles_for_ids(case_ids))
    titles.update(policies.titles_for_ids(policy_ids))
    return titles


def _to_document_counts(by_status: dict[str, int]) -> DocumentCounts:
    return DocumentCounts(total=sum(by_status.values()), by_status=by_status)


# ---------------------------------------------------------------------------
# Read models
# ---------------------------------------------------------------------------


def build_overview() -> OverviewResponse:
    """Document counts, job counts, the live queue and stuck documents."""
    case_counts = cases.count_cases_by_status()
    policy_counts = policies.count_policies_by_status()
    job_counts = ingestion_jobs.count_jobs_by_status()

    active_rows = ingestion_jobs.list_active_jobs()
    active = [_to_job_summary(row, _resolve_titles(active_rows)) for row in active_rows]

    stuck = [
        _to_stuck_document(row, "case") for row in cases.list_processing_cases()
    ] + [_to_stuck_document(row, "policy") for row in policies.list_processing_policies()]

    return OverviewResponse(
        documents=DocumentCountsByType(
            cases=_to_document_counts(case_counts),
            policies=_to_document_counts(policy_counts),
        ),
        jobs=job_counts,
        queue=QueueSnapshot(
            active=active,
            stuck=stuck,
            queued_count=sum(1 for job in active if job.status == "queued"),
            running_count=sum(1 for job in active if job.status == "running"),
        ),
        last_ingest_at=ingestion_jobs.latest_finished_at(),
        generated_at=datetime.now(UTC).isoformat(),
    )


def build_storage() -> StorageResponse:
    """Qdrant collection stats, chunk-row counts and stored policy files."""
    settings = get_settings()
    dims = settings.embedding_dims

    specs = (
        (settings.qdrant_cases_collection, "case"),
        (settings.qdrant_policies_collection, "policy"),
    )

    collections = []
    for name, doc_type in specs:
        # `collection_stats` never raises — an unreachable vector store still
        # produces a row, so the Supabase half of this response survives it.
        stats = qdrant_store.collection_stats(name)
        collections.append(
            CollectionStorage(
                name=stats["name"],
                doc_type=doc_type,
                status=stats["status"],
                reachable=stats["reachable"],
                point_count=stats["points_count"],
                indexed_vector_count=stats["indexed_vectors_count"],
                segment_count=stats["segments_count"],
                estimated_vector_bytes=stats["points_count"] * dims * BYTES_PER_DIMENSION,
            )
        )

    return StorageResponse(
        collections=collections,
        chunk_rows=ChunkRowCounts(
            case_chunks=chunks.count_chunks("case_chunks"),
            policy_chunks=chunks.count_chunks("policy_chunks"),
        ),
        stored_policy_files=policies.count_policies_with_storage(),
        embedding_dims=dims,
    )


def build_job_page(
    *,
    status: str | None,
    doc_type: str | None,
    search: str | None,
    limit: int,
    offset: int,
) -> JobPage:
    """One page of the ingestion ops log, with document titles resolved."""
    rows, total = ingestion_jobs.list_jobs(
        status=status, doc_type=doc_type, search=search, limit=limit, offset=offset
    )
    titles = _resolve_titles(rows)

    return JobPage(
        items=[_to_job_summary(row, titles) for row in rows],
        total=total,
        limit=limit,
        offset=offset,
    )


def build_ingestion_summary(days: int) -> IngestionSummaryResponse:
    """Per-day buckets, duration percentiles and success rate over a window."""
    since = datetime.now(UTC) - timedelta(days=days)
    rows = ingestion_jobs.list_jobs_since(since.isoformat())

    return IngestionSummaryResponse(
        range_days=days,
        per_day=_bucket_by_day(rows, days),
        durations=_duration_stats(rows),
        success_rate=_success_rate(rows),
        by_doc_type={
            "case": sum(1 for row in rows if row["doc_type"] == "case"),
            "policy": sum(1 for row in rows if row["doc_type"] == "policy"),
        },
        by_department=_department_counts(),
    )


def build_document_options(doc_type: str, limit: int) -> list[DocumentOption]:
    """The single-document ingest picker's contents."""
    rows = (
        cases.list_case_options(limit)
        if doc_type == "case"
        else policies.list_policy_options(limit)
    )
    return [
        DocumentOption(
            id=row["id"],
            title=row.get("title") or row["id"],
            doc_type=doc_type,
            status=row["status"],
        )
        for row in rows
    ]


# ---------------------------------------------------------------------------
# Aggregation helpers
# ---------------------------------------------------------------------------


def _bucket_by_day(rows: list[dict], days: int) -> list[DailyJobCount]:
    """Counts per status per day, zero-filled across the whole window.

    Zero-filling is not cosmetic: a sparse series makes a line chart interpolate
    across missing days, which draws activity that never happened.
    """
    today = datetime.now(UTC).date()
    buckets: dict[str, dict[str, int]] = {
        (today - timedelta(days=offset)).isoformat(): dict.fromkeys(
            ingestion_jobs.JOB_STATUSES, 0
        )
        for offset in range(days)
    }

    for row in rows:
        try:
            day = _parse_iso(row["created_at"]).date().isoformat()
        except (KeyError, TypeError, ValueError):
            continue
        bucket = buckets.get(day)
        if bucket is not None and row["status"] in bucket:
            bucket[row["status"]] += 1

    return [
        DailyJobCount(date=day, values=values)
        for day, values in sorted(buckets.items())
    ]


def _duration_stats(rows: list[dict]) -> DurationStats:
    durations = sorted(
        duration for row in rows if (duration := _duration_ms(row)) is not None
    )
    return DurationStats(
        p50_ms=_percentile(durations, 0.5),
        p95_ms=_percentile(durations, 0.95),
        max_ms=durations[-1] if durations else None,
        samples=len(durations),
    )


def _percentile(sorted_values: list[int], fraction: float) -> int | None:
    """Nearest-rank percentile. Null on an empty sample, never 0."""
    if not sorted_values:
        return None
    index = min(len(sorted_values) - 1, int(len(sorted_values) * fraction))
    return sorted_values[index]


def _success_rate(rows: list[dict]) -> float | None:
    """done / (done + failed), or None when nothing finished.

    None rather than 0.0 or 1.0: "no jobs ran" and "every job failed" are very
    different facts, and collapsing them would put a green 100% on an idle
    system.
    """
    done = sum(1 for row in rows if row["status"] == "done")
    failed = sum(1 for row in rows if row["status"] == "failed")
    total = done + failed
    return done / total if total else None


def _department_counts() -> list[DepartmentCount]:
    """Indexed cases per department, labelled, including departments at zero.

    Zero-count departments are kept: an absent bar is ambiguous between "no
    cases" and "department not tracked", and the twelve routing targets are a
    fixed set worth showing in full.
    """
    counts = cases.count_cases_by_department()
    rows = departments.list_departments()

    return [
        DepartmentCount(
            department=row["id"],
            label=row.get("name") or row["id"],
            cases=counts.get(row["id"], 0),
        )
        for row in rows
    ]


def build_departments() -> list[DepartmentOption]:
    """The twelve routing targets, for the escalate picker."""
    return [
        DepartmentOption(id=row["id"], name=row.get("name") or row["id"])
        for row in departments.list_departments()
    ]


# ---------------------------------------------------------------------------
# Escalation — the north-star metric
# ---------------------------------------------------------------------------

# The three things a ticket does that a per-day chart cares about. Not ticket
# *statuses*: `created` and `resolved` are events, and a ticket contributes to
# more than one bucket over its life.
ESCALATION_SERIES: tuple[str, ...] = ("created", "escalated", "resolved")


def _bucket_tickets_by_day(rows: list[dict], days: int) -> list[DailyJobCount]:
    """Per-day created / escalated / resolved counts, zero-filled.

    Separate from `_bucket_by_day` rather than a generalisation of it, because
    the two bucket on different things: that one puts each row in exactly one
    bucket keyed by its status, while a ticket lands in `created` on one date and
    `resolved` on another. Folding them together would need a per-key date
    accessor, which is more machinery than two small functions.

    `escalated` is counted at *resolution* time, from `resolution_path`, so this
    series and the headline rate are computed from the same fact. Counting it at
    escalation time instead would need the `ticket_events` log, and the two
    numbers would then disagree for every still-open escalation.
    """
    today = datetime.now(UTC).date()
    buckets: dict[str, dict[str, int]] = {
        (today - timedelta(days=offset)).isoformat(): dict.fromkeys(ESCALATION_SERIES, 0)
        for offset in range(days)
    }

    for row in rows:
        try:
            created = _parse_iso(row["created_at"]).date().isoformat()
        except (KeyError, TypeError, ValueError):
            continue
        if (bucket := buckets.get(created)) is not None:
            bucket["created"] += 1

        resolved_at = row.get("resolved_at")
        if not resolved_at:
            continue
        try:
            resolved = _parse_iso(resolved_at).date().isoformat()
        except (TypeError, ValueError):
            continue
        if (bucket := buckets.get(resolved)) is not None:
            bucket["resolved"] += 1
            if row.get("resolution_path") == "escalated":
                bucket["escalated"] += 1

    return [DailyJobCount(date=day, values=values) for day, values in sorted(buckets.items())]


def _escalation_rate(direct: int, escalated: int) -> float | None:
    """escalated / (direct + escalated), or None when nothing has resolved.

    None rather than 0.0, for the same reason as `_success_rate`: an empty
    `tickets` table and a table where every complaint was answered first-line
    are opposite facts, and rendering both as "0% escalation" would report the
    system's best possible result for a system that has done nothing.
    """
    total = direct + escalated
    return escalated / total if total else None


def build_escalation_summary(days: int) -> EscalationSummaryResponse:
    """The escalation metric: rate, funnel, trend and per-department split.

    cms.md §2 calls this the north star — "the % of complaints where retrieval +
    draft was not enough and a department had to be contacted. Every improvement
    should push it down." lld.md:257 names the column it reads.
    """
    since = (datetime.now(UTC) - timedelta(days=days)).isoformat()

    by_status = tickets.count_tickets_by_status()
    by_path = tickets.count_by_resolution_path()
    dept_counts = tickets.count_escalations_by_department()
    recent = tickets.list_tickets_since(since)

    direct = by_path.get("direct", 0)
    escalated = by_path.get("escalated", 0)

    # Zero-count departments are kept, matching `_department_counts`: a missing
    # bar cannot be distinguished from a department nobody escalates to, and the
    # second is the interesting one.
    department_rows = departments.list_departments()

    corpus = cases.count_by_resolution_path()

    return EscalationSummaryResponse(
        range_days=days,
        escalation_rate=_escalation_rate(direct, escalated),
        resolved_direct=direct,
        resolved_escalated=escalated,
        open_escalated=tickets.count_open_escalated(),
        total_tickets=sum(by_status.values()),
        by_status=by_status,
        per_day=_bucket_tickets_by_day(recent, days),
        by_department=[
            EscalationByDepartment(
                department=row["id"],
                label=row.get("name") or row["id"],
                escalations=dept_counts.get(row["id"], 0),
            )
            for row in department_rows
        ],
        corpus=CorpusResolutionSplit(
            direct=corpus.get("direct", 0),
            escalated=corpus.get("escalated", 0),
        ),
    )
