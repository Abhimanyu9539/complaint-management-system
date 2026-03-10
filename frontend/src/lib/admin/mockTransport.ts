/**
 * Simulated admin backend.
 *
 * Every shape produced here is normative — it is the contract
 * `backend/docs/admin-api.md` specifies and the real backend must satisfy.
 * Change a field here and change that document in the same commit.
 *
 * Two behaviours are deliberate rather than incidental:
 *
 * 1. Triggered jobs actually progress. `triggerIngestion` inserts a `queued`
 *    row and transitions it to `running` then `done` on wall-clock timers, so
 *    the progress UI, the pulsing status dot and the duration column are all
 *    genuinely exercised in mock mode instead of being dead code until a
 *    backend exists.
 * 2. Latency is simulated per call. A panel that returns instantly never shows
 *    its skeleton, so loading states would ship untested.
 */

import { newId } from '@/lib/id';
import { durationBetween } from '@/lib/format';
import {
  MOCK_ACTIVE_JOBS,
  MOCK_DEPARTMENTS,
  MOCK_DOCUMENT_COUNTS,
  MOCK_JOB_POOL,
  MOCK_RUN_POOL,
  MOCK_STUCK_DOCUMENTS,
  MOCK_TICKETS,
  buildApiUsage,
  buildDepartmentCounts,
  buildDocumentOptions,
  buildEscalationSummary,
  buildTicketEvents,
} from './mockData';
import { AdminRequestError } from './errors';
import type {
  AdminOverview,
  AdminResult,
  AdminTransport,
  AgentRun,
  AgentRunQuery,
  ApiUsageSummary,
  DailyBucket,
  DepartmentOption,
  DocType,
  DocumentOption,
  EscalationSummary,
  IngestionJob,
  IngestionSummary,
  JobQuery,
  JobStatus,
  Page,
  StorageUsage,
  SystemHealth,
  TriggerIngestionRequest,
  TriggerIngestionResponse,
} from './types';
import type {
  Ticket,
  TicketDetail,
  TicketEvent,
  TicketQuery,
  TicketStatus,
} from '@/lib/tickets/types';

/** `ticket_service.ALLOWED`, narrowed to the two edges this UI can drive. */
const ESCALATABLE = new Set<TicketStatus>(['new', 'drafted', 'needs_review', 'dept_responded']);
const RESOLVABLE = new Set<TicketStatus>([
  'new',
  'drafted',
  'needs_review',
  'escalated',
  'dept_responded',
]);

const EMBEDDING_DIMS = 1536;

/** Why each simulated payload is simulated. Surfaced verbatim by `MockBadge`. */
const NOTES = {
  everything: 'Simulated — no backend configured. Set VITE_API_BASE_URL to use live data.',
  trigger:
    'Simulated — ingestion runs as a CLI job today (uv run cms-seed). No POST route exists yet.',
  agent:
    'Simulated — the RAG graph in lld.md §6 has not been built, so there are no runs to report.',
  apiUsage:
    'Simulated — nothing counts API requests today. Wiring this requires ASGI middleware, not a query.',
};

/**
 * Resolves after `ms`, or rejects with AbortError if the caller gives up first.
 * Mirrors the helper in `lib/chat/mockTransport.ts`.
 */
function delay(ms: number, signal: AbortSignal): Promise<void> {
  return new Promise((resolve, reject) => {
    if (signal.aborted) {
      reject(abortError());
      return;
    }
    const timer = setTimeout(resolve, ms);
    signal.addEventListener(
      'abort',
      () => {
        clearTimeout(timer);
        reject(abortError());
      },
      { once: true },
    );
  });
}

function abortError(): DOMException {
  return new DOMException('Aborted', 'AbortError');
}

function result<T>(data: T, note = NOTES.everything): AdminResult<T> {
  return { data, mocked: true, fetchedAt: new Date().toISOString(), note };
}

/**
 * Jobs created during this session, newest first.
 *
 * Module-level rather than per-transport so a triggered job survives a page
 * navigation within the SPA — an operator who triggers an ingest and then opens
 * the dashboard should still see it running.
 */
const sessionJobs: IngestionJob[] = [];

/** Timers for in-flight simulated jobs, so they can be cleared on completion. */
const jobTimers = new Map<string, ReturnType<typeof setTimeout>[]>();

/**
 * Walks a simulated job through queued → running → done.
 *
 * Durations are chosen to be long enough to observe (the queued state is
 * visible for a beat, running for several seconds) but short enough that a
 * developer is not waiting on it.
 */
function scheduleJobProgress(job: IngestionJob, docType: DocType): void {
  const timers: ReturnType<typeof setTimeout>[] = [];

  timers.push(
    setTimeout(() => {
      job.status = 'running';
      job.startedAt = new Date().toISOString();
    }, 1400),
  );

  const workMs = docType === 'policy' ? 9000 : 4200;
  timers.push(
    setTimeout(() => {
      job.status = 'done';
      job.finishedAt = new Date().toISOString();
      job.chunkCount = docType === 'policy' ? 18 : 1;
      job.pointCount = job.chunkCount;
      job.durationMs = durationBetween(job.startedAt, job.finishedAt);
      jobTimers.delete(job.id);
    }, 1400 + workMs),
  );

  jobTimers.set(job.id, timers);
}

/** All jobs the mock knows about: session-created first, then the fixed pool. */
function allJobs(): IngestionJob[] {
  return [...sessionJobs, ...MOCK_ACTIVE_JOBS, ...MOCK_JOB_POOL];
}

function paginate<T>(items: T[], limit: number, offset: number): Page<T> {
  return {
    items: items.slice(offset, offset + limit),
    total: items.length,
    limit,
    offset,
  };
}

// ---------------------------------------------------------------------------
// Methods
// ---------------------------------------------------------------------------

async function getSystemHealth(signal: AbortSignal): Promise<AdminResult<SystemHealth>> {
  await delay(180 + Math.random() * 220, signal);

  return result<SystemHealth>({
    overall: 'ok',
    services: [
      { name: 'API', status: 'ok', detail: 'Simulated response' },
      { name: 'Supabase', status: 'ok', detail: 'Simulated response' },
      { name: 'Qdrant', status: 'ok', detail: 'Simulated response' },
    ],
    checkedAt: new Date().toISOString(),
  });
}

async function getOverview(signal: AbortSignal): Promise<AdminResult<AdminOverview>> {
  await delay(240 + Math.random() * 260, signal);

  const jobs = allJobs();
  const active = jobs.filter((job) => job.status === 'queued' || job.status === 'running');

  const jobCounts: Record<JobStatus, number> = { queued: 0, running: 0, done: 0, failed: 0 };
  for (const job of jobs) jobCounts[job.status] += 1;

  const lastFinished = jobs
    .filter((job) => job.finishedAt)
    .sort((a, b) => (a.finishedAt! < b.finishedAt! ? 1 : -1))[0];

  return result<AdminOverview>({
    documents: MOCK_DOCUMENT_COUNTS,
    jobs: jobCounts,
    queue: {
      active,
      stuck: MOCK_STUCK_DOCUMENTS,
      queuedCount: active.filter((job) => job.status === 'queued').length,
      runningCount: active.filter((job) => job.status === 'running').length,
    },
    lastIngestAt: lastFinished?.finishedAt ?? null,
    generatedAt: new Date().toISOString(),
  });
}

async function getStorageUsage(signal: AbortSignal): Promise<AdminResult<StorageUsage>> {
  await delay(320 + Math.random() * 300, signal);

  const casePoints = 41;
  const policyPoints = 126;

  return result<StorageUsage>({
    collections: [
      {
        name: 'cases_v1',
        docType: 'case',
        status: 'green',
        reachable: true,
        pointCount: casePoints,
        indexedVectorCount: casePoints,
        segmentCount: 2,
        estimatedVectorBytes: casePoints * EMBEDDING_DIMS * 4,
      },
      {
        name: 'policies_v1',
        docType: 'policy',
        status: 'green',
        reachable: true,
        pointCount: policyPoints,
        indexedVectorCount: policyPoints,
        segmentCount: 3,
        estimatedVectorBytes: policyPoints * EMBEDDING_DIMS * 4,
      },
    ],
    // Deliberately two points short of the chunk rows: Postgres is written
    // before Qdrant, so this is exactly what an interrupted upsert looks like,
    // and the drift indicator needs a reason to fire during development.
    chunkRows: { caseChunks: 41, policyChunks: 128 },
    storedPolicyFiles: 5,
    embeddingDims: EMBEDDING_DIMS,
  });
}

async function listIngestionJobs(
  query: JobQuery,
  signal: AbortSignal,
): Promise<AdminResult<Page<IngestionJob>>> {
  await delay(200 + Math.random() * 240, signal);

  const search = query.search?.trim().toLowerCase() ?? '';
  const filtered = allJobs().filter((job) => {
    if (query.status && query.status !== 'all' && job.status !== query.status) return false;
    if (query.docType && query.docType !== 'all' && job.docType !== query.docType) return false;
    if (search) {
      const haystack = `${job.documentTitle ?? ''} ${job.documentId} ${job.id}`.toLowerCase();
      if (!haystack.includes(search)) return false;
    }
    return true;
  });

  return result(paginate(filtered, query.limit, query.offset));
}

async function getIngestionSummary(
  rangeDays: number,
  signal: AbortSignal,
): Promise<AdminResult<IngestionSummary>> {
  await delay(260 + Math.random() * 280, signal);

  const cutoff = Date.now() - rangeDays * 86_400_000;
  const inRange = allJobs().filter((job) => Date.parse(job.createdAt) >= cutoff);

  // Zero-fill every day in range. A sparse series would make the line chart
  // interpolate across missing days and imply activity that never happened.
  const buckets = new Map<string, DailyBucket>();
  for (let index = rangeDays - 1; index >= 0; index -= 1) {
    const date = new Date(Date.now() - index * 86_400_000).toISOString().slice(0, 10);
    buckets.set(date, { date, values: { queued: 0, running: 0, done: 0, failed: 0 } });
  }

  for (const job of inRange) {
    const key = job.createdAt.slice(0, 10);
    const bucket = buckets.get(key);
    if (bucket) bucket.values[job.status] += 1;
  }

  const durations = inRange
    .map((job) => job.durationMs)
    .filter((value): value is number => value !== null)
    .sort((a, b) => a - b);

  const percentile = (fraction: number): number | null => {
    if (durations.length === 0) return null;
    const index = Math.min(durations.length - 1, Math.floor(durations.length * fraction));
    return durations[index];
  };

  const done = inRange.filter((job) => job.status === 'done').length;
  const failed = inRange.filter((job) => job.status === 'failed').length;

  return result<IngestionSummary>({
    rangeDays,
    perDay: [...buckets.values()],
    durations: {
      p50Ms: percentile(0.5),
      p95Ms: percentile(0.95),
      maxMs: durations.at(-1) ?? null,
      samples: durations.length,
    },
    successRate: done + failed === 0 ? null : done / (done + failed),
    byDocType: {
      case: inRange.filter((job) => job.docType === 'case').length,
      policy: inRange.filter((job) => job.docType === 'policy').length,
    },
    byDepartment: buildDepartmentCounts(),
  });
}

async function listDocumentOptions(
  docType: DocType,
  signal: AbortSignal,
): Promise<AdminResult<DocumentOption[]>> {
  await delay(160 + Math.random() * 180, signal);
  return result(buildDocumentOptions(docType));
}

async function triggerIngestion(
  req: TriggerIngestionRequest,
  signal: AbortSignal,
): Promise<AdminResult<TriggerIngestionResponse>> {
  await delay(420 + Math.random() * 320, signal);

  const job: IngestionJob = {
    id: `job-${newId()}`,
    docType: req.docType,
    documentId: req.documentId ?? `${req.docType === 'case' ? 'case' : 'pol'}-seed`,
    documentTitle:
      req.mode === 'seed'
        ? `Seed corpus — all ${req.docType === 'case' ? 'cases' : 'policies'}`
        : (buildDocumentOptions(req.docType).find((option) => option.id === req.documentId)
            ?.title ?? req.documentId ?? 'Unknown document'),
    status: 'queued',
    error: null,
    chunkCount: 0,
    pointCount: 0,
    langsmithRunId: null,
    createdAt: new Date().toISOString(),
    startedAt: null,
    finishedAt: null,
    durationMs: null,
  };

  sessionJobs.unshift(job);
  scheduleJobProgress(job, req.docType);

  return result<TriggerIngestionResponse>(
    {
      jobId: job.id,
      accepted: true,
      message: `Queued a ${req.mode === 'seed' ? 'full re-seed' : 'single-document ingest'} for ${req.docType === 'case' ? 'cases' : 'policies'}${req.force ? ' with the content-hash check bypassed' : ''}.`,
    },
    NOTES.trigger,
  );
}

async function retryJob(
  jobId: string,
  signal: AbortSignal,
): Promise<AdminResult<TriggerIngestionResponse>> {
  await delay(380 + Math.random() * 280, signal);

  const original = allJobs().find((job) => job.id === jobId);
  if (!original) {
    return result<TriggerIngestionResponse>(
      { jobId, accepted: false, message: 'That job no longer exists.' },
      NOTES.trigger,
    );
  }

  const retried: IngestionJob = {
    ...original,
    id: `job-${newId()}`,
    status: 'queued',
    error: null,
    chunkCount: 0,
    pointCount: 0,
    createdAt: new Date().toISOString(),
    startedAt: null,
    finishedAt: null,
    durationMs: null,
  };

  sessionJobs.unshift(retried);
  scheduleJobProgress(retried, original.docType);

  return result<TriggerIngestionResponse>(
    {
      jobId: retried.id,
      accepted: true,
      message: `Re-queued ${original.documentTitle ?? original.documentId}.`,
    },
    NOTES.trigger,
  );
}

async function listAgentRuns(
  query: AgentRunQuery,
  signal: AbortSignal,
): Promise<AdminResult<Page<AgentRun>>> {
  await delay(220 + Math.random() * 260, signal);

  const search = query.search?.trim().toLowerCase() ?? '';
  const fromMs = query.from ? Date.parse(query.from) : null;
  const toMs = query.to ? Date.parse(query.to) : null;

  const filtered = MOCK_RUN_POOL.filter((run) => {
    if (query.status && query.status !== 'all' && run.status !== query.status) return false;
    if (query.actionType && query.actionType !== 'all') {
      if (!run.actions.some((action) => action.type === query.actionType)) return false;
    }
    if (search) {
      const haystack = `${run.inputSummary} ${run.outputSummary ?? ''} ${run.id}`.toLowerCase();
      if (!haystack.includes(search)) return false;
    }
    const startedMs = Date.parse(run.startedAt);
    if (fromMs !== null && startedMs < fromMs) return false;
    if (toMs !== null && startedMs > toMs) return false;
    return true;
  });

  return result(paginate(filtered, query.limit, query.offset), NOTES.agent);
}

async function getAgentRun(
  runId: string,
  signal: AbortSignal,
): Promise<AdminResult<AgentRun | null>> {
  await delay(180 + Math.random() * 200, signal);
  return result(MOCK_RUN_POOL.find((run) => run.id === runId) ?? null, NOTES.agent);
}

async function getApiUsage(
  rangeDays: number,
  signal: AbortSignal,
): Promise<AdminResult<ApiUsageSummary>> {
  await delay(240 + Math.random() * 240, signal);
  return result(buildApiUsage(rangeDays), NOTES.apiUsage);
}

// ---------------------------------------------------------------------------
// Tickets
//
// These exist only for a build with no backend at all. Every ticket method is
// overridden by `realTransport`, so a configured deployment never reaches them
// — which matters, because a simulated ticket queue in front of a real one
// would hide genuine complaints behind a badge nobody investigates.
//
// The store is mutable and the actions actually apply, for the same reason
// `scheduleJobProgress` exists: a demo where escalate does nothing leaves the
// escalate path untested until it meets production.
// ---------------------------------------------------------------------------

const mockTickets: Ticket[] = [...MOCK_TICKETS];
const mockTicketEvents = new Map<string, TicketEvent[]>(
  MOCK_TICKETS.map((ticket) => [ticket.id, buildTicketEvents(ticket)]),
);

let mockEventId = 10_000;

function appendMockEvent(ticketId: string, event: string, payload: Record<string, unknown>): void {
  const events = mockTicketEvents.get(ticketId) ?? [];
  events.push({
    id: (mockEventId += 1),
    event,
    payload,
    actorId: null,
    createdAt: new Date().toISOString(),
  });
  mockTicketEvents.set(ticketId, events);
}

function findMockTicket(ticketId: string): Ticket {
  const ticket = mockTickets.find((candidate) => candidate.id === ticketId);
  if (!ticket) throw new Error('No such ticket.');
  return ticket;
}

async function listTickets(
  query: TicketQuery,
  signal: AbortSignal,
): Promise<AdminResult<Page<Ticket>>> {
  await delay(200 + Math.random() * 220, signal);

  const search = query.search?.trim().toLowerCase();
  const filtered = mockTickets.filter((ticket) => {
    if (query.status && query.status !== 'all' && ticket.status !== query.status) return false;
    if (query.severity && query.severity !== 'all' && ticket.severity !== query.severity) {
      return false;
    }
    if (search) {
      const haystack = `${ticket.subject} ${ticket.customerEmail ?? ''}`.toLowerCase();
      if (!haystack.includes(search)) return false;
    }
    return true;
  });

  return result(paginate(filtered, query.limit, query.offset));
}

async function getTicket(
  ticketId: string,
  signal: AbortSignal,
): Promise<AdminResult<TicketDetail>> {
  await delay(160 + Math.random() * 180, signal);
  const ticket = findMockTicket(ticketId);
  return result({ ticket, events: mockTicketEvents.get(ticketId) ?? [] });
}

async function escalateTicket(
  ticketId: string,
  departmentId: string,
  note: string | null,
  signal: AbortSignal,
): Promise<AdminResult<Ticket>> {
  await delay(320 + Math.random() * 260, signal);

  const ticket = findMockTicket(ticketId);
  // The same guard the backend's state machine applies, so the 409 path is
  // reachable in mock mode instead of only being discovered in production.
  if (!ESCALATABLE.has(ticket.status)) {
    throw new AdminRequestError(
      `A ticket at '${ticket.status}' cannot move to 'escalated'.`,
      409,
    );
  }

  ticket.status = 'escalated';
  ticket.escalatedDept = departmentId;
  ticket.updatedAt = new Date().toISOString();
  appendMockEvent(ticketId, 'escalated', { department_id: departmentId, note });

  return result(ticket);
}

async function resolveTicket(
  ticketId: string,
  note: string | null,
  signal: AbortSignal,
): Promise<AdminResult<Ticket>> {
  await delay(320 + Math.random() * 260, signal);

  const ticket = findMockTicket(ticketId);
  if (!RESOLVABLE.has(ticket.status)) {
    throw new AdminRequestError(`A ticket at '${ticket.status}' cannot move to 'resolved'.`, 409);
  }

  // Derived, never chosen — mirroring `ticket_service._resolution_path_for`.
  const path = ticket.escalatedDept ? 'escalated' : 'direct';
  ticket.status = 'resolved';
  ticket.resolutionPath = path;
  ticket.resolvedAt = new Date().toISOString();
  ticket.updatedAt = ticket.resolvedAt;
  appendMockEvent(ticketId, 'resolved', { resolution_path: path, note });

  return result(ticket);
}

async function getEscalationSummary(
  rangeDays: number,
  signal: AbortSignal,
): Promise<AdminResult<EscalationSummary>> {
  await delay(260 + Math.random() * 240, signal);
  return result(buildEscalationSummary(mockTickets, rangeDays));
}

async function listDepartments(signal: AbortSignal): Promise<AdminResult<DepartmentOption[]>> {
  await delay(120 + Math.random() * 140, signal);
  return result(MOCK_DEPARTMENTS.map((entry) => ({ id: entry.id, name: entry.label })));
}

export function createMockAdminTransport(): AdminTransport {
  return {
    getSystemHealth,
    getOverview,
    getStorageUsage,
    listIngestionJobs,
    getIngestionSummary,
    listDocumentOptions,
    triggerIngestion,
    retryJob,
    listAgentRuns,
    getAgentRun,
    getApiUsage,
    listTickets,
    getTicket,
    escalateTicket,
    resolveTicket,
    getEscalationSummary,
    listDepartments,
  };
}

/** Department label lookup, shared with the pages so ids never leak into the UI. */
export function departmentLabel(id: string | null): string {
  if (!id) return 'Unrouted';
  return MOCK_DEPARTMENTS.find((department) => department.id === id)?.label ?? id;
}
