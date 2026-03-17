/**
 * Live admin transport. Every `AdminTransport` method hits a real route —
 * see `backend/docs/admin-api.md` for the endpoint each one calls.
 *
 * Error handling deliberately diverges from `lib/chat/realTransport.ts`. Chat
 * swallows failures and returns an empty list, because an empty session list is
 * a harmless degraded state. An admin dashboard silently showing zeros during
 * an outage is not harmless: "0 documents indexed" and "we could not reach the
 * API" must never look the same. So failures throw, `useAsyncData` catches, and
 * the last known-good data stays on screen behind an error strip.
 */

import type {
  AdminOverview,
  AdminResult,
  AdminTransport,
  DepartmentOption,
  DocStatus,
  DocType,
  DocumentOption,
  EscalationSummary,
  IngestionJob,
  IngestionSummary,
  JobQuery,
  Page,
  StorageUsage,
  SystemHealth,
  TriggerIngestionRequest,
  TriggerIngestionResponse,
} from './types';
import type { Ticket, TicketDetail, TicketEvent, TicketQuery } from '@/lib/tickets/types';
import { AdminRequestError } from './errors';

function isAbort(err: unknown): boolean {
  return err instanceof DOMException && err.name === 'AbortError';
}

/**
 * One fetch + parse, with every failure mode mapped to an `AdminRequestError`
 * carrying a message an operator can act on.
 */
async function getJson<T>(url: string, signal: AbortSignal): Promise<T> {
  let response: Response;
  try {
    response = await fetch(url, { signal, headers: { Accept: 'application/json' } });
  } catch (err) {
    if (isAbort(err)) throw err;
    console.warn(`admin: request to ${url} failed`, err);
    throw new AdminRequestError(
      'Could not reach the API.',
      null,
      err instanceof Error ? err.message : String(err),
    );
  }

  if (!response.ok) {
    // FastAPI puts a readable string in `detail`; anything else (an HTML error
    // page from a proxy, say) is truncated rather than dumped into the UI.
    let detail: string | undefined;
    try {
      const body = await response.text();
      detail = body.slice(0, 200);
      const parsed: unknown = JSON.parse(body);
      if (parsed && typeof parsed === 'object' && 'detail' in parsed) {
        detail = String((parsed as { detail: unknown }).detail);
      }
    } catch {
      // Body unreadable — the status code alone still tells the operator enough.
    }
    throw new AdminRequestError(
      response.status >= 500
        ? 'The API could not serve this right now.'
        : `Request failed (${response.status}).`,
      response.status,
      detail,
    );
  }

  try {
    return (await response.json()) as T;
  } catch (err) {
    if (isAbort(err)) throw err;
    throw new AdminRequestError(
      'The API returned a response this page could not read.',
      response.status,
      err instanceof Error ? err.message : undefined,
    );
  }
}

function live<T>(data: T): AdminResult<T> {
  return { data, fetchedAt: new Date().toISOString() };
}

/**
 * One POST + parse. Same failure mapping as `getJson`, plus the two statuses
 * only the write endpoints produce.
 *
 * 409 and 422 carry a message the backend wrote for a person — the state
 * machine's "a ticket at 'resolved' cannot move to 'resolved'", or the name of
 * the department that does not exist. Those are passed through verbatim rather
 * than replaced with a generic string, because a generic string turns an
 * explained refusal back into a mystery.
 */
async function postJson<T>(url: string, body: unknown, signal: AbortSignal): Promise<T> {
  let response: Response;
  try {
    response = await fetch(url, {
      method: 'POST',
      signal,
      headers: { 'Content-Type': 'application/json', Accept: 'application/json' },
      body: JSON.stringify(body),
    });
  } catch (err) {
    if (isAbort(err)) throw err;
    console.warn(`admin: request to ${url} failed`, err);
    throw new AdminRequestError(
      'Could not reach the API.',
      null,
      err instanceof Error ? err.message : String(err),
    );
  }

  if (!response.ok) {
    let detail: string | undefined;
    try {
      const parsed = (await response.json()) as { detail?: unknown };
      if (typeof parsed.detail === 'string') detail = parsed.detail;
    } catch {
      // Unreadable body — the status still shapes a usable message.
    }

    if (response.status === 409 || response.status === 422) {
      throw new AdminRequestError(detail ?? 'That action was refused.', response.status, detail);
    }
    if (response.status === 404) {
      // Callers write specific 404s (ticket, job, …); `detail` is the
      // backend's own `HTTPException` string, so this generic fallback is
      // rarely what actually renders.
      throw new AdminRequestError(detail ?? 'That item no longer exists.', 404, detail);
    }
    throw new AdminRequestError(
      response.status >= 500
        ? 'The API could not complete that action right now.'
        : `Request failed (${response.status}).`,
      response.status,
      detail,
    );
  }

  return (await response.json()) as T;
}

// ---------------------------------------------------------------------------
// Wire shapes — snake_case, exactly as the backend emits them
// ---------------------------------------------------------------------------

interface WireJob {
  id: string;
  doc_type: DocType;
  document_id: string;
  document_title: string | null;
  status: IngestionJob['status'];
  error: string | null;
  chunk_count: number;
  point_count: number;
  langsmith_run_id: string | null;
  created_at: string;
  started_at: string | null;
  finished_at: string | null;
  duration_ms: number | null;
}

interface WireJobPage {
  items: WireJob[];
  total: number;
  limit: number;
  offset: number;
}

interface WireTriggerResponse {
  job_id: string;
  accepted: boolean;
  message: string;
}

interface WireDocumentCounts {
  total: number;
  by_status: Record<DocStatus, number>;
}

interface WireStuckDocument {
  id: string;
  doc_type: DocType;
  title: string;
  status: DocStatus;
  since: string;
}

interface WireHealthDeps {
  status: 'ok' | 'degraded';
  dependencies: Record<string, string>;
}

interface WireTicket {
  id: string;
  ticket_no: number;
  status: Ticket['status'];
  severity: Ticket['severity'];
  subject: string;
  body: string | null;
  source: Ticket['source'];
  customer_email: string | null;
  predicted_dept: string | null;
  dept_confidence: number | null;
  escalated_dept: string | null;
  category: string | null;
  resolution_path: Ticket['resolutionPath'];
  created_at: string;
  updated_at: string;
  resolved_at: string | null;
}

interface WireTicketEvent {
  id: number;
  event: string;
  payload: Record<string, unknown>;
  actor_id: string | null;
  created_at: string;
}

function toTicket(wire: WireTicket): Ticket {
  return {
    id: wire.id,
    ticketNo: wire.ticket_no,
    status: wire.status,
    severity: wire.severity,
    subject: wire.subject,
    body: wire.body,
    source: wire.source,
    customerEmail: wire.customer_email,
    predictedDept: wire.predicted_dept,
    deptConfidence: wire.dept_confidence,
    escalatedDept: wire.escalated_dept,
    category: wire.category,
    resolutionPath: wire.resolution_path,
    createdAt: wire.created_at,
    updatedAt: wire.updated_at,
    resolvedAt: wire.resolved_at,
  };
}

function toTicketEvent(wire: WireTicketEvent): TicketEvent {
  return {
    id: wire.id,
    event: wire.event,
    payload: wire.payload,
    actorId: wire.actor_id,
    createdAt: wire.created_at,
  };
}

function toDocumentCounts(wire: WireDocumentCounts): AdminOverview['documents']['cases'] {
  return {
    total: wire.total,
    // Defaults to `{}` rather than trusting the key is always present — a
    // status the backend never returned for this window must read as 0, not
    // crash every panel that indexes into it.
    byStatus: wire.by_status ?? {},
  };
}

function toStuckDocument(wire: WireStuckDocument): AdminOverview['queue']['stuck'][number] {
  return {
    id: wire.id,
    docType: wire.doc_type,
    title: wire.title,
    status: wire.status,
    since: wire.since,
  };
}

function toJob(wire: WireJob): IngestionJob {
  return {
    id: wire.id,
    docType: wire.doc_type,
    documentId: wire.document_id,
    documentTitle: wire.document_title,
    status: wire.status,
    error: wire.error,
    chunkCount: wire.chunk_count,
    pointCount: wire.point_count,
    langsmithRunId: wire.langsmith_run_id,
    createdAt: wire.created_at,
    startedAt: wire.started_at,
    finishedAt: wire.finished_at,
    durationMs: wire.duration_ms,
  };
}

export function createRealAdminTransport(baseUrl: string): AdminTransport {
  const api = `${baseUrl}/api/v1/admin`;
  // Tickets sit outside `/admin` because the create endpoint is customer-facing
  // — see `routes/tickets.py`. The admin panel only reads and acts on them.
  const tickets = `${baseUrl}/api/v1/tickets`;

  /**
   * Health is the one endpoint that must not throw on a dependency failure —
   * a red Qdrant tile *is* the answer, not an error. Only an unreachable API
   * is a genuine failure here.
   */
  async function getSystemHealth(signal: AbortSignal): Promise<AdminResult<SystemHealth>> {
    const wire = await getJson<WireHealthDeps>(`${baseUrl}/health/deps`, signal);

    const services = Object.entries(wire.dependencies).map(([name, value]) => ({
      name: name.charAt(0).toUpperCase() + name.slice(1),
      status: value === 'ok' ? ('ok' as const) : ('error' as const),
      detail: value === 'ok' ? null : value,
    }));

    return live<SystemHealth>({
      overall: wire.status === 'ok' ? 'ok' : 'degraded',
      // The API answered, so it is up by definition — worth stating explicitly
      // so the tile row reads as a complete picture rather than one with a hole.
      services: [{ name: 'API', status: 'ok', detail: null }, ...services],
      checkedAt: new Date().toISOString(),
    });
  }

  async function getOverview(signal: AbortSignal): Promise<AdminResult<AdminOverview>> {
    const wire = await getJson<{
      documents: { cases: WireDocumentCounts; policies: WireDocumentCounts };
      jobs: AdminOverview['jobs'];
      queue: {
        active: WireJob[];
        stuck: WireStuckDocument[];
        queued_count: number;
        running_count: number;
      };
      last_ingest_at: string | null;
      generated_at: string;
    }>(`${api}/overview`, signal);

    return live<AdminOverview>({
      documents: {
        cases: toDocumentCounts(wire.documents.cases),
        policies: toDocumentCounts(wire.documents.policies),
      },
      jobs: wire.jobs,
      queue: {
        active: wire.queue.active.map(toJob),
        stuck: wire.queue.stuck.map(toStuckDocument),
        queuedCount: wire.queue.queued_count,
        runningCount: wire.queue.running_count,
      },
      lastIngestAt: wire.last_ingest_at,
      generatedAt: wire.generated_at,
    });
  }

  async function getStorageUsage(signal: AbortSignal): Promise<AdminResult<StorageUsage>> {
    const wire = await getJson<{
      collections: {
        name: string;
        doc_type: DocType;
        status: StorageUsage['collections'][number]['status'];
        reachable: boolean;
        point_count: number;
        indexed_vector_count: number;
        segment_count: number;
        estimated_vector_bytes: number;
      }[];
      chunk_rows: { case_chunks: number; policy_chunks: number };
      stored_policy_files: number;
      embedding_dims: number;
    }>(`${api}/storage`, signal);

    return live<StorageUsage>({
      collections: wire.collections.map((collection) => ({
        name: collection.name,
        docType: collection.doc_type,
        status: collection.status,
        reachable: collection.reachable,
        pointCount: collection.point_count,
        indexedVectorCount: collection.indexed_vector_count,
        segmentCount: collection.segment_count,
        estimatedVectorBytes: collection.estimated_vector_bytes,
      })),
      chunkRows: {
        caseChunks: wire.chunk_rows.case_chunks,
        policyChunks: wire.chunk_rows.policy_chunks,
      },
      storedPolicyFiles: wire.stored_policy_files,
      embeddingDims: wire.embedding_dims,
    });
  }

  async function listIngestionJobs(
    query: JobQuery,
    signal: AbortSignal,
  ): Promise<AdminResult<Page<IngestionJob>>> {
    const params = new URLSearchParams({
      limit: String(query.limit),
      offset: String(query.offset),
    });
    if (query.status && query.status !== 'all') params.set('status', query.status);
    if (query.docType && query.docType !== 'all') params.set('doc_type', query.docType);
    if (query.search?.trim()) params.set('search', query.search.trim());

    const wire = await getJson<WireJobPage>(`${api}/ingestion/jobs?${params}`, signal);

    return live<Page<IngestionJob>>({
      items: wire.items.map(toJob),
      total: wire.total,
      limit: wire.limit,
      offset: wire.offset,
    });
  }

  async function getIngestionSummary(
    rangeDays: number,
    signal: AbortSignal,
  ): Promise<AdminResult<IngestionSummary>> {
    const wire = await getJson<{
      range_days: number;
      per_day: IngestionSummary['perDay'];
      durations: { p50_ms: number | null; p95_ms: number | null; max_ms: number | null; samples: number };
      success_rate: number | null;
      by_doc_type: IngestionSummary['byDocType'];
      by_department: IngestionSummary['byDepartment'];
    }>(`${api}/ingestion/summary?days=${rangeDays}`, signal);

    return live<IngestionSummary>({
      rangeDays: wire.range_days,
      perDay: wire.per_day,
      durations: {
        p50Ms: wire.durations.p50_ms,
        p95Ms: wire.durations.p95_ms,
        maxMs: wire.durations.max_ms,
        samples: wire.durations.samples,
      },
      successRate: wire.success_rate,
      byDocType: wire.by_doc_type,
      byDepartment: wire.by_department,
    });
  }

  async function listDocumentOptions(
    docType: DocType,
    signal: AbortSignal,
  ): Promise<AdminResult<DocumentOption[]>> {
    const wire = await getJson<{
      items: {
        source_ref: string;
        title: string;
        doc_type: DocType;
        status: DocumentOption['status'];
      }[];
    }>(`${api}/documents?doc_type=${docType}&limit=200`, signal);

    return live(
      wire.items.map((item) => ({
        sourceRef: item.source_ref,
        title: item.title,
        docType: item.doc_type,
        status: item.status,
      })),
    );
  }

  async function triggerIngestion(
    req: TriggerIngestionRequest,
    signal: AbortSignal,
  ): Promise<AdminResult<TriggerIngestionResponse>> {
    const wire = await postJson<WireTriggerResponse>(
      `${api}/ingestion/jobs`,
      {
        doc_type: req.docType,
        mode: req.mode,
        source_ref: req.mode === 'document' ? (req.sourceRef ?? null) : null,
      },
      signal,
    );
    return live<TriggerIngestionResponse>({
      jobId: wire.job_id,
      accepted: wire.accepted,
      message: wire.message,
    });
  }

  async function retryJob(
    jobId: string,
    signal: AbortSignal,
  ): Promise<AdminResult<TriggerIngestionResponse>> {
    const wire = await postJson<WireTriggerResponse>(
      `${api}/ingestion/jobs/${encodeURIComponent(jobId)}/retry`,
      {},
      signal,
    );
    return live<TriggerIngestionResponse>({
      jobId: wire.job_id,
      accepted: wire.accepted,
      message: wire.message,
    });
  }

  async function rerunStuckDocument(
    docType: DocType,
    documentId: string,
    signal: AbortSignal,
  ): Promise<AdminResult<TriggerIngestionResponse>> {
    const wire = await postJson<WireTriggerResponse>(
      `${api}/documents/${encodeURIComponent(docType)}/${encodeURIComponent(documentId)}/rerun`,
      {},
      signal,
    );
    return live<TriggerIngestionResponse>({
      jobId: wire.job_id,
      accepted: wire.accepted,
      message: wire.message,
    });
  }

  // -------------------------------------------------------------------------
  // Tickets
  // -------------------------------------------------------------------------

  async function listTickets(
    query: TicketQuery,
    signal: AbortSignal,
  ): Promise<AdminResult<Page<Ticket>>> {
    const params = new URLSearchParams({
      limit: String(query.limit),
      offset: String(query.offset),
    });
    if (query.status && query.status !== 'all') params.set('status', query.status);
    if (query.severity && query.severity !== 'all') params.set('severity', query.severity);
    if (query.search?.trim()) params.set('search', query.search.trim());

    const wire = await getJson<{
      items: WireTicket[];
      total: number;
      limit: number;
      offset: number;
    }>(`${tickets}?${params}`, signal);

    return live<Page<Ticket>>({
      items: wire.items.map(toTicket),
      total: wire.total,
      limit: wire.limit,
      offset: wire.offset,
    });
  }

  async function getTicket(
    ticketId: string,
    signal: AbortSignal,
  ): Promise<AdminResult<TicketDetail>> {
    const wire = await getJson<{ ticket: WireTicket; events: WireTicketEvent[] }>(
      `${tickets}/${encodeURIComponent(ticketId)}`,
      signal,
    );

    return live<TicketDetail>({
      ticket: toTicket(wire.ticket),
      events: wire.events.map(toTicketEvent),
    });
  }

  async function escalateTicket(
    ticketId: string,
    departmentId: string,
    note: string | null,
    signal: AbortSignal,
  ): Promise<AdminResult<Ticket>> {
    const wire = await postJson<WireTicket>(
      `${tickets}/${encodeURIComponent(ticketId)}/escalate`,
      { department_id: departmentId, note },
      signal,
    );
    return live(toTicket(wire));
  }

  async function resolveTicket(
    ticketId: string,
    note: string | null,
    signal: AbortSignal,
  ): Promise<AdminResult<Ticket>> {
    // No resolution path in the body on purpose — the backend derives it. See
    // `AdminTransport.resolveTicket`.
    const wire = await postJson<WireTicket>(
      `${tickets}/${encodeURIComponent(ticketId)}/resolve`,
      { note },
      signal,
    );
    return live(toTicket(wire));
  }

  async function getEscalationSummary(
    rangeDays: number,
    signal: AbortSignal,
  ): Promise<AdminResult<EscalationSummary>> {
    const wire = await getJson<{
      range_days: number;
      escalation_rate: number | null;
      resolved_direct: number;
      resolved_escalated: number;
      open_escalated: number;
      total_tickets: number;
      by_status: Record<string, number>;
      per_day: EscalationSummary['perDay'];
      by_department: EscalationSummary['byDepartment'];
      corpus: EscalationSummary['corpus'];
    }>(`${api}/escalation?days=${rangeDays}`, signal);

    return live<EscalationSummary>({
      rangeDays: wire.range_days,
      // Passed through untouched, including null. Coercing it to 0 here would
      // undo the whole point of the backend returning null.
      escalationRate: wire.escalation_rate,
      resolvedDirect: wire.resolved_direct,
      resolvedEscalated: wire.resolved_escalated,
      openEscalated: wire.open_escalated,
      totalTickets: wire.total_tickets,
      byStatus: wire.by_status,
      perDay: wire.per_day,
      byDepartment: wire.by_department,
      corpus: wire.corpus,
    });
  }

  async function listDepartments(signal: AbortSignal): Promise<AdminResult<DepartmentOption[]>> {
    const wire = await getJson<{ items: DepartmentOption[] }>(`${api}/departments`, signal);
    return live(wire.items);
  }

  return {
    getSystemHealth,
    getOverview,
    getStorageUsage,
    listIngestionJobs,
    getIngestionSummary,
    listDocumentOptions,
    triggerIngestion,
    retryJob,
    rerunStuckDocument,
    listTickets,
    getTicket,
    escalateTicket,
    resolveTicket,
    getEscalationSummary,
    listDepartments,
  };
}
