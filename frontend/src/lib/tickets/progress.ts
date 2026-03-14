/**
 * "Where has this ticket got to" — derived, never guessed, from real data.
 *
 * The canonical path is `ticket_service.ALLOWED` (lld.md §2) flattened into six
 * stages: Received → Classified → Drafted → Escalated → Dept replied →
 * Resolved. A stage is `done` only when a matching `ticket_events` row says so.
 * Deriving "Classified ✓" from `ticket.status` alone would put a tick next to a
 * classifier that does not exist yet (`rag/` is an empty package) — today only
 * `created`, `escalated` and `resolved` are ever written, so most tickets show
 * gaps, and those gaps are the truth.
 *
 * Pure and side-effect free so the four-state logic is testable without a DOM.
 */

import type { Ticket, TicketEvent, TicketStatus } from './types';

export type ProgressStepId =
  | 'received'
  | 'classified'
  | 'drafted'
  | 'escalated'
  | 'dept_replied'
  | 'resolved';

export type ProgressStepState = 'done' | 'current' | 'skipped' | 'pending';

export interface ProgressStep {
  id: ProgressStepId;
  label: string;
  state: ProgressStepState;
  /** ISO timestamp the step completed. Null unless `state === 'done'`. */
  at: string | null;
}

export interface TicketProgress {
  steps: ProgressStep[];
  /**
   * A `processing_failed` ticket is not paused *on* a stage — it fell off the
   * path. The tracker renders a banner for this rather than a pulsing dot.
   */
  failed: boolean;
}

interface StepDef {
  id: ProgressStepId;
  label: string;
  /** The `ticket_events.event` value that marks this stage done. */
  event: string;
}

const STEPS: readonly StepDef[] = [
  { id: 'received', label: 'Received', event: 'created' },
  { id: 'classified', label: 'Classified', event: 'classified' },
  { id: 'drafted', label: 'Drafted', event: 'drafted' },
  { id: 'escalated', label: 'Escalated', event: 'escalated' },
  { id: 'dept_replied', label: 'Dept replied', event: 'dept_responded' },
  { id: 'resolved', label: 'Resolved', event: 'resolved' },
];

/**
 * The step a ticket's own status names as "home" — where the status implies it
 * last landed, independent of whether that step's event has logged yet. Used
 * both as the starting point for finding the *next undone* step (`current`)
 * and as the frontier for deciding which un-done earlier steps were skipped
 * rather than merely pending.
 */
const STATUS_STEP_INDEX: Record<TicketStatus, number> = {
  new: 0,
  processing: 1,
  drafted: 2,
  needs_review: 2,
  escalated: 3,
  dept_responded: 4,
  resolved: 5,
  processing_failed: 1,
};

/** No pulsing "current" dot for a status that has already ended the ticket's life. */
const TERMINAL_STATUSES = new Set<TicketStatus>(['resolved']);

function lastEventAt(events: readonly TicketEvent[], eventName: string): string | null {
  let latest: string | null = null;
  let latestMs = -Infinity;
  for (const event of events) {
    if (event.event !== eventName) continue;
    const ms = Date.parse(event.createdAt);
    if (Number.isNaN(ms) || ms < latestMs) continue;
    latestMs = ms;
    latest = event.createdAt;
  }
  return latest;
}

/**
 * When the audit trail is silent, two stages still have an authoritative
 * fallback timestamp on the ticket row itself: a ticket that exists was
 * necessarily received (`created_at`), and a ticket the backend calls
 * `resolved` was necessarily resolved (`resolved_at`) even if — defensively —
 * its `resolved` event row is missing (or, in the fully defensive case,
 * `resolved_at` is missing too, and the step is still `done`, just undated).
 * Every other stage has no such column, so an absent event there means the
 * stage genuinely has not happened.
 */
function stepDoneAt(
  step: StepDef,
  ticket: Ticket,
  events: readonly TicketEvent[],
): { done: boolean; at: string | null } {
  const fromEvent = lastEventAt(events, step.event);
  if (fromEvent) return { done: true, at: fromEvent };
  if (step.id === 'received') return { done: true, at: ticket.createdAt };
  if (step.id === 'resolved' && ticket.status === 'resolved') {
    return { done: true, at: ticket.resolvedAt };
  }
  return { done: false, at: null };
}

export function buildProgress(ticket: Ticket, events: readonly TicketEvent[]): TicketProgress {
  const failed = ticket.status === 'processing_failed';
  const frontier = STATUS_STEP_INDEX[ticket.status] ?? 0;
  const showCurrent = !failed && !TERMINAL_STATUSES.has(ticket.status);

  const done = STEPS.map((step) => stepDoneAt(step, ticket, events));

  // The status's home step is often already `done` (a ticket can only reach
  // `dept_responded` once the `dept_replied` step's event has fired) — so
  // "current" is the first *undone* step at or after that point, not the home
  // step itself.
  let currentIndex = -1;
  if (showCurrent) {
    for (let index = frontier; index < STEPS.length; index += 1) {
      if (!done[index].done) {
        currentIndex = index;
        break;
      }
    }
  }

  const steps: ProgressStep[] = STEPS.map((step, index) => {
    if (done[index].done) {
      return { id: step.id, label: step.label, state: 'done', at: done[index].at };
    }
    if (index === currentIndex) {
      return { id: step.id, label: step.label, state: 'current', at: null };
    }
    if (index < frontier) {
      return { id: step.id, label: step.label, state: 'skipped', at: null };
    }
    return { id: step.id, label: step.label, state: 'pending', at: null };
  });

  return { steps, failed };
}
