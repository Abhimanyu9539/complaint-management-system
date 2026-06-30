/**
 * The ticket domain, shared by both audiences.
 *
 * A ticket is read by the admin panel and written by the customer form, and the
 * two go through different transports on purpose: the customer page must not
 * import `lib/admin`, which spreads a mock implementation across six methods
 * that have no backend. So the *types* live here, in neither, and both sides
 * import them.
 *
 * Wire format is snake_case and camelCased at each transport boundary, exactly
 * as `lib/chat` and `lib/admin` already do.
 */

/** `tickets.status` (migration 0004). The lifecycle in lld.md §2. */
export type TicketStatus =
  | 'new'
  | 'processing'
  | 'drafted'
  | 'needs_review'
  | 'escalated'
  | 'dept_responded'
  | 'resolved'
  | 'processing_failed';

export type TicketSeverity = 'low' | 'normal' | 'high' | 'critical';

/**
 * What the customer form offers. `critical` is absent deliberately — a public
 * urgency picker that offers the top of the scale is a picker where everything
 * is critical. Triage raises it, which keeps the label worth something.
 */
export type CustomerSeverity = 'low' | 'normal' | 'high';

/** `tickets.source` (migration 0017). */
export type TicketSource = 'email' | 'web' | 'agent';

/**
 * Path A or Path B (cms.md §1.2). Null until the ticket is resolved, and that
 * null means "not yet decided" rather than "direct" — the escalation rate is
 * computed only over non-null values.
 */
export type ResolutionPath = 'direct' | 'escalated';

export interface DeptCandidate {
  department: string;
  score: number;
}

export interface Ticket {
  id: string;
  /** The customer-facing reference, rendered as `T-1042`. */
  ticketNo: number;
  status: TicketStatus;
  severity: TicketSeverity;
  subject: string;
  /** Null for a ticket created before migration 0017, or ingested subject-only. */
  body: string | null;
  source: TicketSource;
  customerEmail: string | null;
  /** The classifier's top department. Null until the ticket graph has run. */
  predictedDept: string | null;
  deptConfidence: number | null;
  /** Every department the classifier considered, best first, scores summing to 1. */
  deptCandidates: DeptCandidate[];
  /** The classifier's suggestion; `severity` changes only when a person confirms it. */
  suggestedSeverity: TicketSeverity | null;
  /** Why the gate sent this ticket to `needs_review`, in plain words. Empty otherwise. */
  reviewReasons: string[];
  /** Identifiers copied from the complaint, keyed `order_no`, `product`, ... */
  entities: Record<string, string>;
  /** The department actually escalated to. Non-null implies Path B. */
  escalatedDept: string | null;
  category: string | null;
  resolutionPath: ResolutionPath | null;
  createdAt: string;
  updatedAt: string;
  resolvedAt: string | null;
}

/**
 * One row of the append-only audit log (`ticket_events`, migration 0016).
 *
 * `event` is a bare string rather than a union because the column carries no
 * CHECK constraint — narrowing it here would make the UI throw away rows a
 * future writer emits, which is the opposite of what an audit log is for.
 */
export interface TicketEvent {
  id: number;
  event: string;
  payload: Record<string, unknown>;
  /** Null means the system acted rather than a person. */
  actorId: string | null;
  createdAt: string;
}

/** A past case the drafter was offered. `marker` is its `[n]` in the draft. */
export interface CaseEvidence {
  marker: number;
  caseId: string;
  chunkId: string;
  title: string;
  snippet: string;
  resolution: string | null;
  /** Hybrid (RRF) score: ranks cases within one ticket, not a similarity. */
  score: number;
  cited: boolean;
}

/** A policy chunk the drafter was offered. `marker` is its `[n]` in the draft. */
export interface PolicyEvidence {
  marker: number;
  policyId: string;
  chunkId: string;
  title: string;
  section: string;
  snippet: string;
  /** Reranker score, 0–1. */
  score: number;
  cited: boolean;
}

/** A department's answer the drafter was offered. `marker` is its `[n]` in the draft. */
export interface GuidanceEvidence {
  marker: number;
  /** For an earlier department answer from a past case, the case id. */
  deptResponseId: string;
  departmentId: string;
  title: string;
  snippet: string;
  cited: boolean;
}

/** A question drafted for a department; the agent edits it before escalating. */
export interface DeptQuestion {
  draftId: string;
  departmentId: string;
  text: string;
}

/** Why an agent rejected a draft (`draft_feedback.edit_reason`). */
export type DiscardReason = 'wrong_case' | 'wrong_tone' | 'wrong_policy' | 'other';

/** What an agent did with a draft: sent it as-is, sent it edited, or rejected it. */
export interface DraftFeedback {
  action: 'accepted' | 'edited' | 'rejected';
  /** Exactly what was emailed. Null when rejected. */
  finalText: string | null;
  editReason: DiscardReason | null;
  createdAt: string;
}

/** The latest reply drafted for the customer (`drafts`, kind `customer_reply`). */
export interface TicketDraft {
  id: string;
  version: number;
  /** Keeps its `[n]` markers; they are removed when the reply is sent. */
  draftText: string;
  /** No policy matched, so this is the holding reply. */
  noMatch: boolean;
  /** False: still failed the output guard after one retry. Null: not checked. */
  grounded: boolean | null;
  guardReasons: string[];
  retrievedCases: CaseEvidence[];
  policyRefs: PolicyEvidence[];
  /** The department answers it was written from, after an escalation. Cited first. */
  guidanceRefs: GuidanceEvidence[];
  model: string;
  promptVersion: string;
  createdAt: string;
  /** Null until the draft is sent or discarded. */
  feedback: DraftFeedback | null;
}

export interface TicketDetail {
  ticket: Ticket;
  events: TicketEvent[];
  /** Null until the ticket graph has drafted. */
  draft: TicketDraft | null;
}

export interface TicketQuery {
  status?: TicketStatus | 'all';
  severity?: TicketSeverity | 'all';
  /** Matches subject or customer email. Server-side. */
  search?: string;
  limit: number;
  offset: number;
}

// ---------------------------------------------------------------------------
// Customer intake
// ---------------------------------------------------------------------------

export interface CreateTicketRequest {
  subject: string;
  body: string;
  customerEmail: string;
  severity: CustomerSeverity;
}

export interface TicketCreated {
  id: string;
  ticketNo: number;
  status: TicketStatus;
  createdAt: string;
}

/** Field bounds, mirroring `schemas/tickets.py`. Kept in sync by hand. */
export const TICKET_LIMITS = {
  subjectMin: 3,
  subjectMax: 200,
  bodyMin: 10,
  bodyMax: 8000,
  emailMax: 254,
} as const;
