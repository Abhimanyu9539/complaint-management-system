"""Response contracts for the read-only admin surface.

These are the first DTOs in the codebase, so this module sets the pattern:

- One module per API surface, under `cms/schemas/`.
- Response models only. Request bodies arrive as query parameters today, and
  there is nothing to model until there is a POST.
- Field names are snake_case, matching the wire format exactly. The frontend
  camelCases at its own transport boundary; doing it here would put a
  presentation concern in the schema layer.
- `frozen=True` throughout. A response object is a value, and mutating one after
  construction has never once been the intent.
- `Literal[...]` rather than `Enum` for status fields — it publishes the same
  constraint into the OpenAPI schema without adding a second definition of a
  vocabulary the database already constrains with a CHECK.
"""

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

DocType = Literal["case", "policy"]
DocStatus = Literal["pending", "processing", "indexed", "failed", "deleting"]
JobStatus = Literal["queued", "running", "done", "failed"]
# Qdrant's own green/yellow/grey/red, plus two states of our own:
# `missing` — the server answered but has no such collection (run
# cms-create-collections), and `unknown` — the server could not be reached.
# Distinguished because the remedies are different.
CollectionStatus = Literal["green", "yellow", "grey", "red", "missing", "unknown"]


class _Base(BaseModel):
    model_config = ConfigDict(frozen=True)


# ---------------------------------------------------------------------------
# Documents
# ---------------------------------------------------------------------------


class DocumentCounts(_Base):
    total: int
    by_status: dict[DocStatus, int]


class DocumentCountsByType(_Base):
    cases: DocumentCounts
    policies: DocumentCounts


class DocumentOption(_Base):
    """One entry in the admin's single-document ingest picker."""

    id: str
    title: str
    doc_type: DocType
    status: DocStatus


class DocumentOptionPage(_Base):
    items: list[DocumentOption]


# ---------------------------------------------------------------------------
# Ingestion jobs
# ---------------------------------------------------------------------------


class JobSummary(_Base):
    id: str
    doc_type: DocType
    document_id: str
    document_title: str | None = Field(
        default=None,
        description=(
            "Null when the document has been deleted. `ingestion_jobs` has no FK "
            "on document_id by design — it is an append-only ops log whose rows "
            "outlive the documents they describe — so this is resolved with a "
            "LEFT JOIN and clients must render the bare id rather than a blank."
        ),
    )
    status: JobStatus
    error: str | None = None
    chunk_count: int
    point_count: int
    langsmith_run_id: str | None = None
    created_at: str
    started_at: str | None = None
    finished_at: str | None = None
    duration_ms: int | None = Field(
        default=None,
        description="finished_at − started_at. Null while queued or still running.",
    )


class JobPage(_Base):
    items: list[JobSummary]
    total: int
    limit: int
    offset: int


class StuckDocument(_Base):
    """A document claimed for ingest that never finished.

    The pipeline marks a row `processing` before it starts work, so anything
    left here is the residue of a crashed run — and, because chunk upserts key
    on (document, index) and Qdrant point ids are content-derived, re-running is
    safe rather than merely probably safe.
    """

    id: str
    doc_type: DocType
    title: str
    status: DocStatus
    since: str


class QueueSnapshot(_Base):
    active: list[JobSummary]
    stuck: list[StuckDocument]
    queued_count: int
    running_count: int


class OverviewResponse(_Base):
    documents: DocumentCountsByType
    jobs: dict[JobStatus, int]
    queue: QueueSnapshot
    last_ingest_at: str | None = None
    generated_at: str


# ---------------------------------------------------------------------------
# Storage
# ---------------------------------------------------------------------------


class CollectionStorage(_Base):
    name: str
    doc_type: DocType
    status: CollectionStatus
    reachable: bool
    point_count: int
    indexed_vector_count: int
    segment_count: int
    estimated_vector_bytes: int = Field(
        description=(
            "points × embedding_dims × 4. An ESTIMATE: Qdrant reports no byte "
            "figure, and this excludes payloads, sparse vectors and the HNSW "
            "graph, so treat it as a floor. Clients must label it as estimated."
        )
    )


class ChunkRowCounts(_Base):
    case_chunks: int
    policy_chunks: int


class StorageResponse(_Base):
    collections: list[CollectionStorage]
    chunk_rows: ChunkRowCounts
    stored_policy_files: int = Field(
        description="policies rows with a non-null storage_path — a count of files, not bytes."
    )
    embedding_dims: int


# ---------------------------------------------------------------------------
# Ingestion analytics
# ---------------------------------------------------------------------------


class DailyJobCount(_Base):
    date: str
    values: dict[str, int]


class DurationStats(_Base):
    p50_ms: int | None = None
    p95_ms: int | None = None
    max_ms: int | None = None
    samples: int


class DepartmentCount(_Base):
    department: str
    label: str
    cases: int


class IngestionSummaryResponse(_Base):
    range_days: int
    per_day: list[DailyJobCount] = Field(
        description="One entry per day in range, zero-filled. Gaps would let charts interpolate."
    )
    durations: DurationStats
    success_rate: float | None = Field(
        default=None,
        description="done / (done + failed). Null when nothing finished in range — not 0.",
    )
    by_doc_type: dict[DocType, int]
    by_department: list[DepartmentCount]


# ---------------------------------------------------------------------------
# Escalation — the north-star metric (cms.md §2, §5)
# ---------------------------------------------------------------------------


class DepartmentOption(_Base):
    """One of the twelve routing targets, for the escalate picker."""

    id: str
    name: str


class DepartmentOptionPage(_Base):
    items: list[DepartmentOption]


class EscalationByDepartment(_Base):
    department: str
    label: str
    escalations: int


class CorpusResolutionSplit(_Base):
    """`cases.resolution_path` — how already-resolved complaints were resolved.

    Reported alongside the live ticket figures but never summed with them. A case
    may have been minted from a ticket (the flywheel), and a seeded case was
    never a ticket at all, so adding the two would double-count some complaints
    and invent others.
    """

    direct: int
    escalated: int


class EscalationSummaryResponse(_Base):
    range_days: int
    escalation_rate: float | None = Field(
        default=None,
        description=(
            "escalated / (direct + escalated), over tickets with a non-null "
            "resolution_path. Null — never 0.0 — when no ticket has been "
            "resolved yet: an idle queue and a queue that never escalates are "
            "different facts, and a green 0% on an empty table is the specific "
            "lie this field exists to avoid."
        ),
    )
    resolved_direct: int
    resolved_escalated: int
    open_escalated: int = Field(
        description=(
            "Escalated and still awaiting a department. These have no "
            "resolution_path yet and are excluded from the rate — the outcome "
            "is not known, and counting them would move the metric before it."
        )
    )
    total_tickets: int
    by_status: dict[str, int]
    per_day: list[DailyJobCount] = Field(
        description="Zero-filled per-day counts keyed created / escalated / resolved."
    )
    by_department: list[EscalationByDepartment] = Field(
        description="Includes departments at zero — an absent bar is ambiguous."
    )
    corpus: CorpusResolutionSplit
