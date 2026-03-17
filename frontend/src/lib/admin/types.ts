/**
 * Domain types and the transport contract for the admin panel.
 *
 * These shapes are normative. `backend/docs/admin-api.md` documents the wire
 * format they correspond to and which endpoints are live versus contract-only;
 * changing anything here means changing that document in the same commit.
 *
 * Casing follows the existing frontend convention: wire payloads are snake_case
 * and are mapped to camelCase view models at the transport boundary
 * (`realTransport.ts`), exactly as `lib/chat/` does.
 */

import type { Ticket, TicketDetail, TicketQuery } from '@/lib/tickets/types';

// ---------------------------------------------------------------------------
// Envelope
// ---------------------------------------------------------------------------

/**
 * Every admin payload is wrapped so the UI can always answer "when was this
 * true?" without the call site special-casing anything.
 *
 * The admin transport is real-only — there is no mock fallback, so every
 * value here is a measurement, never a simulation. (Chat and the workbench
 * keep their own mocks; see `lib/chat/transport.ts` and `lib/tickets/simulated.ts`.)
 */
export interface AdminResult<T> {
  data: T;
  /** ISO time the client received it. Drives "Updated 14s ago". */
  fetchedAt: string;
}

/** Server-side paging. `total` is the unfiltered-by-page count, for the pager. */
export interface Page<T> {
  items: T[];
  total: number;
  limit: number;
  offset: number;
}

// ---------------------------------------------------------------------------
// Shared vocabulary — mirrors the CHECK constraints in the Supabase migrations
// ---------------------------------------------------------------------------

export type DocType = 'case' | 'policy';

/** `cases.status` / `policies.status` (migrations 0005, 0006). */
export type DocStatus = 'pending' | 'processing' | 'indexed' | 'failed' | 'deleting';

/** `ingestion_jobs.status` (migration 0012). */
export type JobStatus = 'queued' | 'running' | 'done' | 'failed';

// ---------------------------------------------------------------------------
// Health
// ---------------------------------------------------------------------------

export interface ServiceHealth {
  name: string;
  status: 'ok' | 'error';
  /** The error string when `status === 'error'`, else a short "how" note. */
  detail: string | null;
}

export interface SystemHealth {
  /** `degraded` means some dependency is down but the API itself answered. */
  overall: 'ok' | 'degraded' | 'down';
  services: ServiceHealth[];
  checkedAt: string;
}

// ---------------------------------------------------------------------------
// Documents and the ingest queue
// ---------------------------------------------------------------------------

export interface DocumentCounts {
  total: number;
  byStatus: Record<DocStatus, number>;
}

export interface DocumentCountsByType {
  cases: DocumentCounts;
  policies: DocumentCounts;
}

export interface IngestionJob {
  id: string;
  docType: DocType;
  documentId: string;
  /**
   * `ingestion_jobs` deliberately has no FK on `document_id` — it is an
   * append-only ops log whose rows outlive the documents they describe, so a
   * failed ingest of a since-deleted document remains as evidence. The backend
   * resolves titles with a LEFT JOIN, so this is null for a deleted document
   * and the UI must render the bare id rather than a blank cell.
   */
  documentTitle: string | null;
  status: JobStatus;
  error: string | null;
  chunkCount: number;
  pointCount: number;
  langsmithRunId: string | null;
  createdAt: string;
  startedAt: string | null;
  finishedAt: string | null;
  /** `finishedAt − startedAt` in ms. Null while queued or still running. */
  durationMs: number | null;
}

/**
 * A document left at `processing` with no running job behind it.
 *
 * Not an invented category: the pipeline claims the row *before* it starts
 * work, so a crash between claim and completion leaves the document visibly
 * stuck here. That is the documented recovery signal, and nothing else in the
 * system surfaces it.
 */
export interface StuckDocument {
  id: string;
  docType: DocType;
  title: string;
  /** Always 'processing' — the definition of stuck. Kept for rendering. */
  status: DocStatus;
  /** When it entered `processing`. */
  since: string;
}

export interface QueueSnapshot {
  active: IngestionJob[];
  stuck: StuckDocument[];
  queuedCount: number;
  runningCount: number;
}

export interface AdminOverview {
  documents: DocumentCountsByType;
  jobs: Record<JobStatus, number>;
  queue: QueueSnapshot;
  /** `finished_at` of the most recent completed job, or null if none ever ran. */
  lastIngestAt: string | null;
  generatedAt: string;
}

// ---------------------------------------------------------------------------
// Storage
// ---------------------------------------------------------------------------

export interface CollectionStorage {
  /** The Qdrant collection name, e.g. `cases_v1`. From settings, never hardcoded. */
  name: string;
  docType: DocType;
  /**
   * Qdrant's own green/yellow/grey/red, plus two of ours:
   * - `missing` — the server answered but has no such collection. The fix is
   *   `uv run cms-create-collections`.
   * - `unknown` — Qdrant could not be reached at all. The fix is checking
   *   QDRANT_URL and /health/deps.
   *
   * Kept distinct because reporting both as "unreachable" sends an operator to
   * debug their network when the real remedy is one command.
   */
  status: 'green' | 'yellow' | 'grey' | 'red' | 'missing' | 'unknown';
  /** False only when Qdrant itself is unreachable — a missing collection is still reachable. */
  reachable: boolean;
  pointCount: number;
  indexedVectorCount: number;
  segmentCount: number;
  /**
   * `points × dims × 4`. An ESTIMATE, and every call site must label it as one:
   * Qdrant reports no byte figure, and this excludes payloads, sparse vectors
   * and the HNSW graph, so it is a floor rather than a measurement.
   */
  estimatedVectorBytes: number;
}

export interface StorageUsage {
  collections: CollectionStorage[];
  /**
   * Row counts in `case_chunks` / `policy_chunks`. Drift between these and the
   * Qdrant point counts is a genuine consistency signal — Postgres is written
   * before Qdrant, so chunks > points means an interrupted upsert.
   */
  chunkRows: { caseChunks: number; policyChunks: number };
  /** `policies` rows with a non-null `storage_path` — files in Supabase Storage. */
  storedPolicyFiles: number;
  embeddingDims: number;
}

// ---------------------------------------------------------------------------
// Ingestion analytics
// ---------------------------------------------------------------------------

/** One day of counts, keyed by whatever dimension the caller bucketed on. */
export interface DailyBucket {
  date: string;
  values: Record<string, number>;
}

export interface DurationStats {
  p50Ms: number | null;
  p95Ms: number | null;
  maxMs: number | null;
  /** How many finished jobs the percentiles were computed from. */
  samples: number;
}

export interface DepartmentCount {
  department: string;
  label: string;
  cases: number;
}

export interface IngestionSummary {
  rangeDays: number;
  /** One entry per day in range, keyed by `JobStatus`. Gaps are zero-filled. */
  perDay: DailyBucket[];
  durations: DurationStats;
  /** `done / (done + failed)`. Null when nothing finished in range. */
  successRate: number | null;
  byDocType: Record<DocType, number>;
  byDepartment: DepartmentCount[];
}

// ---------------------------------------------------------------------------
// Agent activity — contract-only; nothing emits these yet
// ---------------------------------------------------------------------------

/**
 * Node names of the planned RAG graph (lld.md §6). Union literals rather than a
 * TS enum, which `erasableSyntaxOnly` forbids.
 *
 * The graph is deliberately tool-less (lld.md §6.4: "it proposes; the human
 * applies"), so no action type here ever represents a write.
 */
export type AgentActionType =
  | 'analyze_query'
  | 'direct_answer'
  | 'retrieve'
  | 'grade_documents'
  | 'rewrite_query'
  | 'generate'
  | 'check_groundedness'
  | 'no_match_response';

export type AgentRunStatus = 'running' | 'succeeded' | 'failed' | 'no_match';

export interface AgentAction {
  id: string;
  type: AgentActionType;
  status: 'ok' | 'failed' | 'skipped';
  startedAt: string;
  durationMs: number;
  /** One line of what this node decided, for the timeline. */
  detail: string;
  /**
   * Loop-guard counter. The graph caps `retrieval_attempts` at 2 and
   * `regenerated` at 1, so rendering `retrieve 2/2` makes the guard legible
   * instead of leaving a repeated node looking like a duplicate log line.
   */
  attempt: number;
}

export interface AgentRun {
  id: string;
  sessionId: string | null;
  startedAt: string;
  finishedAt: string | null;
  status: AgentRunStatus;
  department: string | null;
  /**
   * Department-routing confidence, compared against the backend's
   * `dept_confidence_threshold` (0.60). Null when the run never routed.
   */
  confidence: number | null;
  inputSummary: string;
  outputSummary: string | null;
  actions: AgentAction[];
  langsmithRunId: string | null;
  totalLatencyMs: number | null;
  inputTokens: number | null;
  outputTokens: number | null;
  costUsd: number | null;
}

// ---------------------------------------------------------------------------
// Escalation — the north-star metric (cms.md §2, §5)
// ---------------------------------------------------------------------------

export interface DepartmentOption {
  id: string;
  name: string;
}

export interface EscalationByDepartment {
  department: string;
  label: string;
  escalations: number;
}

/**
 * `cases.resolution_path` — how already-resolved complaints were resolved.
 *
 * Reported next to the live ticket figures but never added to them: a case may
 * have been minted from a ticket by the flywheel, and a seeded case was never a
 * ticket at all, so summing would double-count some complaints and invent
 * others. The UI labels this as the resolved-case corpus, separately.
 */
export interface CorpusResolutionSplit {
  direct: number;
  escalated: number;
}

export interface EscalationSummary {
  rangeDays: number;
  /**
   * `escalated / (direct + escalated)` over resolved tickets. **Null, never 0**,
   * when nothing has resolved yet — an idle queue and a queue that never
   * escalates are opposite facts, and rendering both as 0% would report this
   * system's best possible result for a system that has done nothing. Call
   * sites must render null as "no data".
   */
  escalationRate: number | null;
  resolvedDirect: number;
  resolvedEscalated: number;
  /**
   * Escalated and still waiting on a department. Excluded from the rate: the
   * outcome is not known yet, and counting it would move the metric before it.
   */
  openEscalated: number;
  totalTickets: number;
  byStatus: Record<string, number>;
  /** Zero-filled per-day counts keyed `created` / `escalated` / `resolved`. */
  perDay: DailyBucket[];
  byDepartment: EscalationByDepartment[];
  corpus: CorpusResolutionSplit;
}

// ---------------------------------------------------------------------------
// API usage — contract-only; no request counter exists
// ---------------------------------------------------------------------------

export interface ApiUsagePoint {
  date: string;
  requests: number;
  errors: number;
  p95LatencyMs: number;
}

export interface ApiUsageSummary {
  rangeDays: number;
  points: ApiUsagePoint[];
  totalRequests: number;
  /** 0–1. Errors ÷ requests over the whole range. */
  errorRate: number;
}

// ---------------------------------------------------------------------------
// Queries and mutations
// ---------------------------------------------------------------------------

export interface JobQuery {
  status?: JobStatus | 'all';
  docType?: DocType | 'all';
  /** Matches document title or id. Server-side. */
  search?: string;
  limit: number;
  offset: number;
}

export interface AgentRunQuery {
  status?: AgentRunStatus | 'all';
  actionType?: AgentActionType | 'all';
  search?: string;
  /** ISO date bounds, inclusive. */
  from?: string;
  to?: string;
  limit: number;
  offset: number;
}

export interface TriggerIngestionRequest {
  docType: DocType;
  /** 'seed' re-runs the whole corpus (as `cms-seed` does); 'document' re-seeds one file. */
  mode: 'seed' | 'document';
  /**
   * The seed corpus's natural key (a policy filename or a case id) — not a
   * Postgres id, since a file that has never been seeded has no row yet.
   */
  sourceRef?: string;
}

export interface TriggerIngestionResponse {
  jobId: string;
  /** False when the backend declined — the UI shows `message` as the reason. */
  accepted: boolean;
  message: string;
}

/**
 * A picker entry for "ingest one document". Deliberately minimal.
 *
 * Lists the on-disk seed corpus, not the `cases`/`policies` tables — a
 * partially seeded corpus otherwise looks complete (see `backend/docs/admin-api.md` §3).
 */
export interface DocumentOption {
  /** The seed corpus's natural key (a policy filename or a case id), not a Postgres id. */
  sourceRef: string;
  title: string;
  docType: DocType;
  /** Null when the document has no Postgres row yet — it has never been seeded. */
  status: DocStatus | null;
}

// ---------------------------------------------------------------------------
// Transport
// ---------------------------------------------------------------------------

/**
 * The admin data surface. Real-only — see `AdminResult`. Every method here has
 * a route behind it; `AgentRun`/`ApiUsageSummary` above are kept as the
 * contract for the agent-runs log and API-usage counter once those exist (see
 * `backend/docs/admin-api.md` §6/§7), but neither has a transport method until
 * a backend does.
 */
export interface AdminTransport {
  /**
   * LIVE. Wraps `GET /health/deps` plus the reachability of the API itself.
   * Poll this more slowly than everything else: it makes an outbound HTTP call
   * to GoTrue and a Qdrant handshake on every hit.
   */
  getSystemHealth(signal: AbortSignal): Promise<AdminResult<SystemHealth>>;

  /**
   * LIVE. Document counts, job counts, the active queue and the stuck-document
   * list in one payload — one poll drives the whole dashboard header.
   */
  getOverview(signal: AbortSignal): Promise<AdminResult<AdminOverview>>;

  /** LIVE. Talks to Qdrant, so it is the slowest live call — give it its own interval. */
  getStorageUsage(signal: AbortSignal): Promise<AdminResult<StorageUsage>>;

  /**
   * LIVE. Server-side paged and filtered — the ops log is append-only and grows
   * without bound, so client-side filtering would eventually fetch everything.
   */
  listIngestionJobs(query: JobQuery, signal: AbortSignal): Promise<AdminResult<Page<IngestionJob>>>;

  /** LIVE. Per-day buckets, duration percentiles and success rate for the charts. */
  getIngestionSummary(
    rangeDays: number,
    signal: AbortSignal,
  ): Promise<AdminResult<IngestionSummary>>;

  /** LIVE. Populates the "ingest a single document" picker from the on-disk seed corpus. */
  listDocumentOptions(
    docType: DocType,
    signal: AbortSignal,
  ): Promise<AdminResult<DocumentOption[]>>;

  /**
   * LIVE. Queues a job row and returns immediately (202 semantics) — the
   * embedding run happens in a background task, not inline. See
   * `backend/docs/admin-api.md` §4.
   */
  triggerIngestion(
    req: TriggerIngestionRequest,
    signal: AbortSignal,
  ): Promise<AdminResult<TriggerIngestionResponse>>;

  /** LIVE. Re-ingests the document a finished/failed job referenced, as a new job row. */
  retryJob(jobId: string, signal: AbortSignal): Promise<AdminResult<TriggerIngestionResponse>>;

  /**
   * LIVE. Re-runs a document stuck at `processing` (the dashboard queue
   * panel), by its own Postgres id — distinct from `triggerIngestion`'s
   * `mode: 'document'`, which now names a seed-corpus file by `sourceRef`.
   */
  rerunStuckDocument(
    docType: DocType,
    documentId: string,
    signal: AbortSignal,
  ): Promise<AdminResult<TriggerIngestionResponse>>;

  // -------------------------------------------------------------------------
  // Tickets — all LIVE. The customer form writes real rows, so an ops view of
  // them that could be simulated would be worse than none: an operator cannot
  // tell a mocked empty queue from a real one, and a real complaint would sit
  // unanswered behind a "Simulated" badge nobody investigates.
  // -------------------------------------------------------------------------

  /** LIVE. Server-side paged and filtered; the queue grows without bound. */
  listTickets(query: TicketQuery, signal: AbortSignal): Promise<AdminResult<Page<Ticket>>>;

  /** LIVE. Ticket plus its `ticket_events` audit trail — one request per drawer. */
  getTicket(ticketId: string, signal: AbortSignal): Promise<AdminResult<TicketDetail>>;

  /**
   * LIVE. Hand a ticket to a specialist department (Path B). Rejects with an
   * `AdminRequestError` carrying status 409 when the state machine forbids the
   * move, so the caller can say why rather than "something failed".
   */
  escalateTicket(
    ticketId: string,
    departmentId: string,
    note: string | null,
    signal: AbortSignal,
  ): Promise<AdminResult<Ticket>>;

  /**
   * LIVE. Close a ticket. Takes no resolution path on purpose — the backend
   * derives it from whether the ticket was ever escalated, because a client
   * that could assert it could set the north-star metric by hand.
   */
  resolveTicket(
    ticketId: string,
    note: string | null,
    signal: AbortSignal,
  ): Promise<AdminResult<Ticket>>;

  /** LIVE. The escalation rate, funnel, trend and per-department split. */
  getEscalationSummary(
    rangeDays: number,
    signal: AbortSignal,
  ): Promise<AdminResult<EscalationSummary>>;

  /** LIVE. The closed set of twelve routing targets, for the escalate picker. */
  listDepartments(signal: AbortSignal): Promise<AdminResult<DepartmentOption[]>>;
}
