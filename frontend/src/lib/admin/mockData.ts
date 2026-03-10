/**
 * Deterministic fixtures for the admin panel.
 *
 * Every shape here is normative — it is the contract the backend must emit.
 * Change anything in this file and change `backend/docs/admin-api.md` in the
 * same commit.
 *
 * Determinism matters more than it looks. These generators feed line charts
 * that re-render on a 20-second poll; seeding off `Math.random()` would make
 * every tick redraw a different history, which reads as instability in the
 * system being monitored rather than in the mock. Everything is therefore
 * derived from a fixed seed plus a day index.
 */

import type {
  AgentAction,
  AgentActionType,
  AgentRun,
  AgentRunStatus,
  ApiUsageSummary,
  DailyBucket,
  DocStatus,
  DocType,
  DocumentOption,
  EscalationSummary,
  IngestionJob,
  JobStatus,
  StuckDocument,
} from './types';
import type {
  ResolutionPath,
  Ticket,
  TicketEvent,
  TicketSeverity,
  TicketStatus,
} from '@/lib/tickets/types';

/**
 * A small deterministic PRNG (mulberry32). Seeded per-series so two charts
 * drawing different metrics do not share a sequence and end up correlated.
 */
function seeded(seed: number): () => number {
  let state = seed >>> 0;
  return () => {
    state = (state + 0x6d2b79f5) >>> 0;
    let t = state;
    t = Math.imul(t ^ (t >>> 15), t | 1);
    t ^= t + Math.imul(t ^ (t >>> 7), t | 61);
    return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
  };
}

function randomInt(rand: () => number, min: number, max: number): number {
  return Math.floor(rand() * (max - min + 1)) + min;
}

function pick<T>(rand: () => number, items: readonly T[]): T {
  return items[Math.floor(rand() * items.length)];
}

/** Midnight UTC, `daysAgo` days back — the anchor for every generated series. */
function dayStart(daysAgo: number): Date {
  const date = new Date();
  date.setUTCHours(0, 0, 0, 0);
  date.setUTCDate(date.getUTCDate() - daysAgo);
  return date;
}

function isoMinutesAgo(minutes: number): string {
  return new Date(Date.now() - minutes * 60_000).toISOString();
}

// ---------------------------------------------------------------------------
// Corpus — mirrors the shape of backend/data/seed
// ---------------------------------------------------------------------------

/** The 12 rows seeded by migration 0003. Ids match `departments.id`. */
export const MOCK_DEPARTMENTS: readonly { id: string; label: string }[] = [
  { id: 'warranty', label: 'Warranty' },
  { id: 'billing', label: 'Billing' },
  { id: 'shipping', label: 'Shipping & Logistics' },
  { id: 'product_safety', label: 'Product Safety' },
  { id: 'returns', label: 'Returns' },
  { id: 'tech_support', label: 'Technical Support' },
  { id: 'qa', label: 'Quality Assurance' },
  { id: 'legal', label: 'Legal' },
  { id: 'sales', label: 'Sales' },
  { id: 'manufacturing', label: 'Manufacturing' },
  { id: 'retention', label: 'Customer Retention' },
  { id: 'spare_parts', label: 'Spare Parts' },
];

const CASE_TITLES = [
  'ProBlend 300 — ERR-22 after 40 minutes of use',
  'Duplicate subscription charge, March and April',
  'Delivery marked complete, parcel never arrived',
  'Base plate discoloured after first dishwasher cycle',
  'Replacement jug arrived with a hairline crack',
  'Refund approved but never credited',
  'Motor stalls under load, unit within warranty',
  'Courier left package with no signature',
  'Blade assembly loose out of the box',
  'Charged after cancelling the trial',
  'Thermal cutout triggering on every use',
  'Return label expired before pickup',
  'Warranty claim rejected without an explanation',
  'Spare gasket out of stock for six weeks',
  'Unit arrived with the wrong power adapter',
];

const POLICY_TITLES = [
  'Small Appliance Warranty Policy v2',
  'Billing & Refunds Policy v3',
  'Shipping and Delivery Standards v1',
  'Returns and Exchanges Policy v2',
  'Product Safety Escalation Procedure v1',
];

/**
 * Realistic failure strings, in the exact format the pipeline persists:
 * `f"{type(exc).__name__}: {exc}"`, truncated to 2000 chars. The class name is
 * always the first token, which is what `humaniseIngestError` parses.
 */
const MOCK_ERRORS = [
  'RateLimitError: Rate limit reached for text-embedding-3-small in organization org-xxxx on tokens per min (TPM): Limit 1000000, Used 998321, Requested 4096.',
  'UnexpectedResponse: Unexpected Response: 404 (Not Found)\nRaw response content:\nb\'{"status":{"error":"Collection `policies_v1` doesn\\\'t exist!"},"time":0.000123}\'',
  'ResponseHandlingException: timed out',
  'LookupError: case 8f2a1c04-1d3e-4b7a-9c55-0d1e2f3a4b5c disappeared before ingest finished',
  'APIError: {\'message\': \'new row violates row-level security policy for table "case_chunks"\', \'code\': \'42501\'}',
  'AuthenticationError: Incorrect API key provided: sk-proj-****. You can find your API key at https://platform.openai.com/account/api-keys.',
];

// ---------------------------------------------------------------------------
// Documents
// ---------------------------------------------------------------------------

export const MOCK_DOCUMENT_COUNTS = {
  cases: {
    total: 43,
    byStatus: { indexed: 39, processing: 1, pending: 2, failed: 1, deleting: 0 } as Record<
      DocStatus,
      number
    >,
  },
  policies: {
    total: 8,
    byStatus: { indexed: 7, processing: 0, pending: 0, failed: 1, deleting: 0 } as Record<
      DocStatus,
      number
    >,
  },
};

export function buildDocumentOptions(docType: DocType): DocumentOption[] {
  const rand = seeded(docType === 'case' ? 4021 : 9107);
  const titles = docType === 'case' ? CASE_TITLES : POLICY_TITLES;
  const statuses: DocStatus[] = ['indexed', 'indexed', 'indexed', 'pending', 'failed'];

  return titles.map((title, index) => ({
    id: `${docType === 'case' ? 'case' : 'pol'}-${String(1001 + index)}`,
    title,
    docType,
    status: pick(rand, statuses),
  }));
}

// ---------------------------------------------------------------------------
// Ingestion jobs
// ---------------------------------------------------------------------------

/**
 * A stable pool of ~140 jobs spread over 45 days, newest first.
 *
 * Built once at module load rather than per request so paging through the table
 * is coherent — page 2 must not be a fresh random draw of page 1.
 */
function buildJobPool(): IngestionJob[] {
  const rand = seeded(20260728);
  const jobs: IngestionJob[] = [];

  for (let index = 0; index < 140; index += 1) {
    const docType: DocType = rand() < 0.78 ? 'case' : 'policy';
    const titles = docType === 'case' ? CASE_TITLES : POLICY_TITLES;

    // Newest first: index 0 is minutes old, index 139 is ~45 days old.
    const minutesAgo = Math.round(index * 460 * (0.6 + rand() * 0.8)) + randomInt(rand, 2, 40);

    // ~7% failure rate, which is the interesting-but-not-alarming range that
    // exercises the error UI without making the dashboard look broken.
    const roll = rand();
    const status: JobStatus = roll < 0.07 ? 'failed' : 'done';

    const createdAt = isoMinutesAgo(minutesAgo);
    const startedAt = isoMinutesAgo(minutesAgo - 0.02);
    const durationMs =
      docType === 'policy' ? randomInt(rand, 4200, 38_000) : randomInt(rand, 180, 4800);
    const finishedAt = new Date(Date.parse(startedAt) + durationMs).toISOString();

    const chunkCount = docType === 'policy' ? randomInt(rand, 6, 34) : 1;

    jobs.push({
      id: `job-${String(index).padStart(4, '0')}`,
      docType,
      documentId: `${docType === 'case' ? 'case' : 'pol'}-${String(1001 + (index % titles.length))}`,
      // ~4% of rows point at a document that has since been deleted. This is
      // not noise: the table has no FK by design, so the UI has to render the
      // null-title case, and it will never be exercised if the mock is tidy.
      documentTitle: rand() < 0.04 ? null : titles[index % titles.length],
      status,
      error: status === 'failed' ? pick(rand, MOCK_ERRORS) : null,
      chunkCount: status === 'failed' ? 0 : chunkCount,
      pointCount: status === 'failed' ? 0 : chunkCount,
      langsmithRunId: rand() < 0.8 ? `ls-${Math.floor(rand() * 1e12).toString(16)}` : null,
      createdAt,
      startedAt,
      finishedAt,
      durationMs,
    });
  }

  return jobs;
}

export const MOCK_JOB_POOL: IngestionJob[] = buildJobPool();

/** Jobs currently queued or running — the dashboard's live queue. */
export const MOCK_ACTIVE_JOBS: IngestionJob[] = [
  {
    id: 'job-active-01',
    docType: 'policy',
    documentId: 'pol-1003',
    documentTitle: 'Shipping and Delivery Standards v1',
    status: 'running',
    error: null,
    chunkCount: 0,
    pointCount: 0,
    langsmithRunId: 'ls-9f2c41a0b3',
    createdAt: isoMinutesAgo(3),
    startedAt: isoMinutesAgo(3),
    finishedAt: null,
    durationMs: null,
  },
  {
    id: 'job-active-02',
    docType: 'case',
    documentId: 'case-1012',
    documentTitle: 'Return label expired before pickup',
    status: 'queued',
    error: null,
    chunkCount: 0,
    pointCount: 0,
    langsmithRunId: null,
    createdAt: isoMinutesAgo(1),
    startedAt: null,
    finishedAt: null,
    durationMs: null,
  },
];

/**
 * One document stuck at `processing`.
 *
 * Included on purpose: the pipeline claims a row before it starts work, so this
 * state is what a crashed ingest looks like. If the mock never produced one,
 * the recovery panel would never be seen during development.
 */
export const MOCK_STUCK_DOCUMENTS: StuckDocument[] = [
  {
    id: 'case-1007',
    docType: 'case',
    title: 'Motor stalls under load, unit within warranty',
    status: 'processing',
    since: isoMinutesAgo(214),
  },
];

// ---------------------------------------------------------------------------
// Agent runs — contract-only
// ---------------------------------------------------------------------------

const AGENT_QUERIES = [
  'My ProBlend 300 is showing ERR-22, what should I tell the customer?',
  'Customer was charged twice in March — what does the refund policy allow?',
  'Parcel marked delivered but never arrived. Which department owns this?',
  'Is a hairline crack in the jug covered under warranty?',
  'What is our SLA for a replacement part that is out of stock?',
  'Customer wants a refund outside the 30-day window. Any precedent?',
  'Blade assembly arrived loose — is this a safety escalation?',
  'How do we handle a warranty claim with no proof of purchase?',
  'Courier left the package without a signature. What is our liability?',
  'Thermal cutout keeps triggering — known issue or one-off?',
];

const AGENT_ANSWERS = [
  'ERR-22 indicates a thermal cutout on the motor assembly. Under §3.1 of the Small Appliance Warranty Policy this is covered for 24 months; offer a replacement unit and arrange collection.',
  'Duplicate charges within one billing cycle are refunded in full without manager approval per Billing & Refunds §2.4. Process the reversal and confirm within one business day.',
  'Non-delivery with a courier-confirmed scan routes to Shipping & Logistics. Open a trace before offering a replacement — §4.2 requires the trace reference on the claim.',
  'Cosmetic damage on arrival is treated as transit damage, not a manufacturing defect. Replace the part at no cost and log it against the courier, per Returns §3.',
];

function buildActions(rand: () => number, status: AgentRunStatus, startedAt: string): AgentAction[] {
  const actions: AgentAction[] = [];
  let cursor = Date.parse(startedAt);

  const push = (
    type: AgentActionType,
    detail: string,
    durationMs: number,
    actionStatus: AgentAction['status'] = 'ok',
    attempt = 1,
  ) => {
    actions.push({
      id: `act-${actions.length}-${Math.floor(rand() * 1e6)}`,
      type,
      status: actionStatus,
      startedAt: new Date(cursor).toISOString(),
      durationMs,
      detail,
      attempt,
    });
    cursor += durationMs;
  };

  push('analyze_query', 'Classified as a policy lookup; department predicted.', randomInt(rand, 180, 420));
  push('retrieve', 'Hybrid search over cases_v1 and policies_v1 — 8 candidates.', randomInt(rand, 240, 900));
  push('grade_documents', 'Graded 8 candidates in one batched call; 3 relevant.', randomInt(rand, 300, 700));

  if (status === 'no_match') {
    // The second retrieval attempt is the loop guard doing its job — this is
    // what makes `attempt` worth rendering in the timeline.
    push('rewrite_query', 'No candidate cleared the threshold; broadened the query.', randomInt(rand, 200, 400));
    push('retrieve', 'Second attempt — still nothing above 0.60.', randomInt(rand, 240, 800), 'ok', 2);
    push('no_match_response', 'Returned the cautious holding template.', randomInt(rand, 60, 140));
    return actions;
  }

  if (status === 'failed') {
    push('generate', 'Upstream model call failed after two retries.', randomInt(rand, 1200, 3400), 'failed');
    push('check_groundedness', 'Skipped — no draft to check.', 0, 'skipped');
    return actions;
  }

  push('generate', 'Drafted the answer from 3 grounded chunks.', randomInt(rand, 1400, 4200));
  push('check_groundedness', 'All claims traced to retrieved text.', randomInt(rand, 280, 620));
  return actions;
}

function buildRunPool(): AgentRun[] {
  const rand = seeded(77310);
  const runs: AgentRun[] = [];

  for (let index = 0; index < 96; index += 1) {
    const roll = rand();
    const status: AgentRunStatus =
      roll < 0.06 ? 'failed' : roll < 0.19 ? 'no_match' : 'succeeded';

    const minutesAgo = Math.round(index * 92 * (0.5 + rand() * 1.1)) + randomInt(rand, 1, 25);
    const startedAt = isoMinutesAgo(minutesAgo);
    const actions = buildActions(rand, status, startedAt);
    const totalLatencyMs = actions.reduce((sum, action) => sum + action.durationMs, 0);

    const department = status === 'no_match' ? null : pick(rand, MOCK_DEPARTMENTS).id;
    const confidence =
      status === 'no_match' ? 0.3 + rand() * 0.29 : 0.62 + rand() * 0.37;

    const inputTokens = randomInt(rand, 900, 3600);
    const outputTokens = status === 'failed' ? 0 : randomInt(rand, 120, 640);

    runs.push({
      id: `run-${String(index).padStart(4, '0')}`,
      sessionId: rand() < 0.85 ? `sess-${Math.floor(rand() * 1e8).toString(16)}` : null,
      startedAt,
      finishedAt: new Date(Date.parse(startedAt) + totalLatencyMs).toISOString(),
      status,
      department,
      confidence: Number(confidence.toFixed(2)),
      inputSummary: AGENT_QUERIES[index % AGENT_QUERIES.length],
      outputSummary:
        status === 'succeeded'
          ? AGENT_ANSWERS[index % AGENT_ANSWERS.length]
          : status === 'no_match'
            ? 'No source cleared the retrieval threshold. Returned a holding response rather than an unsupported answer.'
            : null,
      actions,
      langsmithRunId: `ls-${Math.floor(rand() * 1e12).toString(16)}`,
      totalLatencyMs,
      inputTokens,
      outputTokens,
      // gpt-4o-class pricing, order-of-magnitude only.
      costUsd: Number(((inputTokens * 2.5 + outputTokens * 10) / 1_000_000).toFixed(5)),
    });
  }

  return runs;
}

export const MOCK_RUN_POOL: AgentRun[] = buildRunPool();

// ---------------------------------------------------------------------------
// API usage — contract-only
// ---------------------------------------------------------------------------

export function buildApiUsage(rangeDays: number): ApiUsageSummary {
  const rand = seeded(51884 + rangeDays);
  const points = [];

  for (let index = rangeDays - 1; index >= 0; index -= 1) {
    const date = dayStart(index);
    // Weekends run ~40% lighter, which is what makes the series look like
    // traffic rather than noise.
    const weekend = date.getUTCDay() === 0 || date.getUTCDay() === 6;
    const base = weekend ? 180 : 420;
    const requests = randomInt(rand, base, Math.round(base * 1.9));

    points.push({
      date: date.toISOString().slice(0, 10),
      requests,
      errors: randomInt(rand, 0, Math.max(1, Math.round(requests * 0.03))),
      p95LatencyMs: randomInt(rand, 620, 2400),
    });
  }

  const totalRequests = points.reduce((sum, point) => sum + point.requests, 0);
  const totalErrors = points.reduce((sum, point) => sum + point.errors, 0);

  return {
    rangeDays,
    points,
    totalRequests,
    errorRate: totalRequests === 0 ? 0 : totalErrors / totalRequests,
  };
}

/** Cases per department, for the statistics page's department breakdown. */
export function buildDepartmentCounts(): { department: string; label: string; cases: number }[] {
  const rand = seeded(30115);
  return MOCK_DEPARTMENTS.map((department) => ({
    department: department.id,
    label: department.label,
    // Warranty and billing dominate a real complaint corpus; a flat
    // distribution would make the chart useless as a design reference.
    cases: randomInt(rand, department.id === 'warranty' || department.id === 'billing' ? 6 : 0, 12),
  }));
}

// ---------------------------------------------------------------------------
// Tickets
//
// A hand-written pool rather than a generator. Thirteen rows is enough to reach
// every status, and writing them by hand puts the escalation rate on a value
// worth reading: 4 direct and 3 escalated resolutions is 42.9%, high enough to
// look like a problem and specific enough that an off-by-one in the calculation
// is visible. A generated pool drifts towards 50%, where a wrong answer and a
// right one look alike.
// ---------------------------------------------------------------------------

interface TicketSeed {
  subject: string;
  body: string;
  status: TicketStatus;
  severity: TicketSeverity;
  /** The department involved, if any. Drives `escalatedDept` and the Path B split. */
  dept: string | null;
  path: ResolutionPath | null;
}

const TICKET_SEEDS: readonly TicketSeed[] = [
  {
    subject: 'Blender base overheating after 20 minutes',
    body: 'The ProBlend 300 gets too hot to touch after about twenty minutes and then shuts itself off. It has done this three times this week.',
    status: 'new',
    severity: 'high',
    dept: null,
    path: null,
  },
  {
    subject: 'Charged twice for the same order',
    body: 'Order 88213 shows two identical charges of 74.99 on my statement, both dated 3 March.',
    status: 'new',
    severity: 'normal',
    dept: null,
    path: null,
  },
  {
    subject: 'Replacement jug never arrived',
    body: 'Tracking says delivered on the 12th but nothing arrived. I have checked with the neighbours and with the building manager.',
    status: 'needs_review',
    severity: 'normal',
    dept: null,
    path: null,
  },
  {
    subject: 'Lid seal splits under normal use',
    body: 'The silicone seal on the lid has split along the moulding line after six weeks. This looks like a manufacturing defect rather than wear.',
    status: 'escalated',
    severity: 'high',
    dept: 'product_safety',
    path: null,
  },
  {
    subject: 'Warranty claim rejected without explanation',
    body: 'I submitted a claim under the two-year warranty and received a one-line rejection with no reason given.',
    status: 'escalated',
    severity: 'normal',
    dept: 'warranty',
    path: null,
  },
  {
    subject: 'Motor rattles on the highest setting',
    body: 'There is a loud rattle on setting 5 that was not there when the unit was new.',
    status: 'dept_responded',
    severity: 'normal',
    dept: 'qa',
    path: null,
  },
  {
    subject: 'How do I descale the reservoir?',
    body: 'The manual mentions descaling but does not say how often, or what to use.',
    status: 'resolved',
    severity: 'low',
    dept: null,
    path: 'direct',
  },
  {
    subject: 'Missing spare blade from the accessory pack',
    body: 'The pack was listed as containing two blades and arrived with one.',
    status: 'resolved',
    severity: 'normal',
    dept: null,
    path: 'direct',
  },
  {
    subject: 'Wrong colour delivered',
    body: 'Ordered graphite, received white. Otherwise the correct model and everything else was right.',
    status: 'resolved',
    severity: 'low',
    dept: null,
    path: 'direct',
  },
  {
    subject: 'Refund still not received after 14 days',
    body: 'The return was confirmed on the 2nd and I was told five working days.',
    status: 'resolved',
    severity: 'normal',
    dept: null,
    path: 'direct',
  },
  {
    subject: 'Base plate discoloured after one wash',
    body: 'The stainless base has gone a dull brown after a single dishwasher cycle, despite the listing saying dishwasher safe.',
    status: 'resolved',
    severity: 'high',
    dept: 'manufacturing',
    path: 'escalated',
  },
  {
    subject: 'Recall notice — is my unit affected?',
    body: 'I saw a recall notice for a batch of units and my serial number is close to the range listed.',
    status: 'resolved',
    severity: 'critical',
    dept: 'product_safety',
    path: 'escalated',
  },
  {
    subject: 'Extended warranty terms contradict the receipt',
    body: 'The receipt says three years, the website says two. I would like to know which one applies.',
    status: 'resolved',
    severity: 'normal',
    dept: 'legal',
    path: 'escalated',
  },
];

/**
 * The simulated queue, newest first.
 *
 * Ages spread across three weeks so the per-day trend has shape instead of one
 * spike, and each resolved ticket carries a `resolvedAt` a plausible interval
 * after creation. Escalated tickets take substantially longer, because the
 * department round trip is the cost the escalation-rate metric exists to
 * measure — a fixture where both paths resolved equally fast would make the
 * metric look pointless.
 */
export const MOCK_TICKETS: Ticket[] = TICKET_SEEDS.map((entry, index): Ticket => {
  const rand = seeded(90210 + index);
  const createdDaysAgo = randomInt(rand, 0, 20);
  const createdAt = new Date(
    dayStart(createdDaysAgo).getTime() + randomInt(rand, 0, 82_800) * 1000,
  );

  const resolutionHours =
    entry.path === 'escalated' ? randomInt(rand, 26, 96) : randomInt(rand, 1, 14);
  const resolvedAt =
    entry.path === null
      ? null
      : new Date(createdAt.getTime() + resolutionHours * 3_600_000).toISOString();

  return {
    id: `tkt_${String(index + 1).padStart(4, '0')}`,
    ticketNo: 1040 + index,
    status: entry.status,
    severity: entry.severity,
    subject: entry.subject,
    body: entry.body,
    source: 'web',
    customerEmail: `customer${index + 1}@example.com`,
    predictedDept: entry.dept,
    deptConfidence: entry.dept ? 0.62 + rand() * 0.35 : null,
    // Only set once the ticket has actually been escalated. A `new` ticket with
    // a predicted department has not taken Path B, and writing it here would
    // make `_resolution_path_for` classify it as escalated on resolve.
    escalatedDept: entry.status === 'new' ? null : entry.dept,
    category: null,
    resolutionPath: entry.path,
    createdAt: createdAt.toISOString(),
    updatedAt: resolvedAt ?? createdAt.toISOString(),
    resolvedAt,
  };
}).sort((a, b) => Date.parse(b.createdAt) - Date.parse(a.createdAt));

/**
 * A plausible audit trail for a ticket, derived from where it ended up.
 *
 * Reconstructed rather than listed as its own fixture: the real `ticket_events`
 * rows are written as transitions happen, so an independent fixture could
 * disagree with the ticket's own status — a timeline contradicting the badge
 * above it is the one inconsistency this drawer must never show.
 */
export function buildTicketEvents(ticket: Ticket): TicketEvent[] {
  const base = ticket.ticketNo * 10;
  const createdMs = Date.parse(ticket.createdAt);

  const events: TicketEvent[] = [
    {
      id: base,
      event: 'created',
      payload: { source: ticket.source, severity: ticket.severity },
      actorId: null,
      createdAt: ticket.createdAt,
    },
  ];

  if (ticket.escalatedDept) {
    events.push({
      id: base + 1,
      event: 'escalated',
      payload: { department_id: ticket.escalatedDept },
      actorId: null,
      createdAt: new Date(createdMs + 3_600_000).toISOString(),
    });
  }

  if (ticket.status === 'dept_responded') {
    events.push({
      id: base + 2,
      event: 'dept_responded',
      payload: {},
      actorId: null,
      createdAt: new Date(createdMs + 7_200_000).toISOString(),
    });
  }

  if (ticket.resolvedAt) {
    events.push({
      id: base + 3,
      event: 'resolved',
      payload: { resolution_path: ticket.resolutionPath },
      actorId: null,
      createdAt: ticket.resolvedAt,
    });
  }

  return events;
}

/**
 * The escalation metric, computed from the live mock store.
 *
 * Computed rather than fixed, so escalating or resolving a ticket in the UI
 * actually moves the number. A hard-coded figure would sit still while the
 * queue changed underneath it — which is exactly the bug this panel exists to
 * expose in the real implementation, and it would be invisible in the mock that
 * is supposed to be exercising it.
 */
export function buildEscalationSummary(tickets: Ticket[], rangeDays: number): EscalationSummary {
  const direct = tickets.filter((ticket) => ticket.resolutionPath === 'direct').length;
  const escalated = tickets.filter((ticket) => ticket.resolutionPath === 'escalated').length;
  const resolvedTotal = direct + escalated;

  const byStatus: Record<string, number> = {};
  for (const ticket of tickets) {
    byStatus[ticket.status] = (byStatus[ticket.status] ?? 0) + 1;
  }

  // Zero-filled and keyed the same three ways the backend buckets: a ticket
  // lands in `created` on one date and in `resolved` on another, so this is not
  // a status tally.
  const perDay: DailyBucket[] = [];
  for (let index = rangeDays - 1; index >= 0; index -= 1) {
    const date = dayStart(index).toISOString().slice(0, 10);
    perDay.push({
      date,
      values: {
        created: tickets.filter((ticket) => ticket.createdAt.startsWith(date)).length,
        resolved: tickets.filter((ticket) => ticket.resolvedAt?.startsWith(date)).length,
        escalated: tickets.filter(
          (ticket) => ticket.resolvedAt?.startsWith(date) && ticket.resolutionPath === 'escalated',
        ).length,
      },
    });
  }

  const deptCounts = new Map<string, number>();
  for (const ticket of tickets) {
    if (ticket.escalatedDept) {
      deptCounts.set(ticket.escalatedDept, (deptCounts.get(ticket.escalatedDept) ?? 0) + 1);
    }
  }

  return {
    rangeDays,
    // Null rather than 0 on an empty pool, matching the backend exactly. This
    // is the single behaviour most worth mirroring in the mock, because it is
    // the one a reimplementation gets wrong by default.
    escalationRate: resolvedTotal > 0 ? escalated / resolvedTotal : null,
    resolvedDirect: direct,
    resolvedEscalated: escalated,
    openEscalated: tickets.filter(
      (ticket) => ticket.status === 'escalated' || ticket.status === 'dept_responded',
    ).length,
    totalTickets: tickets.length,
    byStatus,
    perDay,
    byDepartment: MOCK_DEPARTMENTS.map((department) => ({
      department: department.id,
      label: department.label,
      escalations: deptCounts.get(department.id) ?? 0,
    })),
    // The seed corpus in `backend/data/seed/cases.json`: 13 direct, 7 escalated.
    corpus: { direct: 13, escalated: 7 },
  };
}
