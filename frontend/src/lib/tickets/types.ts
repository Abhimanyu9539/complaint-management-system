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
  /** The classifier's guess. Null until a classifier exists. */
  predictedDept: string | null;
  deptConfidence: number | null;
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

export interface TicketDetail {
  ticket: Ticket;
  events: TicketEvent[];
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
