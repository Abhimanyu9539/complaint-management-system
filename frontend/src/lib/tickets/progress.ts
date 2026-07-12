/**
 * The ticket's path so far, one row per milestone in the order it happened, then
 * the rows still ahead. Milestones come from `ticket_events`, so a redraft or a
 * second escalation adds a row instead of re-ticking a fixed list. Every other
 * event (gated, failed, discarded) stays in the full event history.
 */

import type { Ticket, TicketEvent } from './types';

export type ProgressStepState = 'done' | 'current' | 'pending';

export interface ProgressStep {
  key: string;
  label: string;
  state: ProgressStepState;
  /** When a done step happened. Null for the rows still ahead. */
  at: string | null;
  /** Shown under a row still ahead, in place of a time. */
  caption: string | null;
}

export interface TicketProgress {
  steps: ProgressStep[];
  /** `processing_failed`: the ticket fell off the pipeline. The tracker shows a banner. */
  failed: boolean;
}

type DepartmentLabel = (id: string | null) => string;

const REPLY_SENT = 'Reply sent';

function done(key: string, label: string, at: string | null): ProgressStep {
  return { key, label, state: 'done', at, caption: null };
}

function ahead(label: string, state: 'current' | 'pending', caption: string): ProgressStep {
  return { key: `ahead-${label}`, label, state, at: null, caption };
}

function departmentOf(event: TicketEvent): string | null {
  const id = event.payload.department_id;
  return typeof id === 'string' ? id : null;
}

/** The milestone rows in `events`, oldest first. */
function milestones(events: readonly TicketEvent[], departmentLabel: DepartmentLabel): ProgressStep[] {
  const sorted = [...events].sort((a, b) => Date.parse(a.createdAt) - Date.parse(b.createdAt));
  const steps: ProgressStep[] = [];
  let classified = false;
  let drafted = false;
  // The department whose answer arrived since the last draft, for the redraft's label.
  let answeredBy: string | null = null;

  for (const event of sorted) {
    const key = String(event.id);
    const at = event.createdAt;
    switch (event.event) {
      case 'created':
        steps.push(done(key, 'Received', at));
        break;
      case 'classified':
        // Every re-run classifies again; the first one is the milestone.
        if (!classified) steps.push(done(key, 'Classified', at));
        classified = true;
        break;
      case 'drafted': {
        const label = !drafted
          ? 'Drafted'
          : answeredBy
            ? `Redrafted from ${answeredBy}'s answer`
            : 'Redrafted';
        steps.push(done(key, label, at));
        drafted = true;
        answeredBy = null;
        break;
      }
      case 'escalated':
        steps.push(done(key, `Escalated to ${departmentLabel(departmentOf(event))}`, at));
        break;
      case 'dept_responded':
        answeredBy = departmentLabel(departmentOf(event));
        steps.push(done(key, `${answeredBy} replied`, at));
        break;
      case 'sent':
        steps.push(done(key, REPLY_SENT, at));
        break;
      case 'resolved':
        // Sending resolves the ticket, so the two read as one step.
        if (steps.at(-1)?.label === REPLY_SENT) {
          steps[steps.length - 1] = done(key, `${REPLY_SENT} · Resolved`, at);
        } else {
          steps.push(done(key, 'Resolved', at));
        }
        break;
      case 'customer_replied':
        steps.push(done(key, 'Customer replied', at));
        break;
      case 'reopened':
        steps.push(done(key, 'Reopened', at));
        break;
      case 'case_minted':
        steps.push(done(key, 'Added to the knowledge base', at));
        break;
      case 'case_removed':
        steps.push(done(key, 'Removed from the knowledge base', at));
        break;
    }
  }
  return steps;
}

/** What is still ahead for a ticket at its status. The first row is current when someone is on it. */
function stepsAhead(
  ticket: Ticket,
  events: readonly TicketEvent[],
  departmentLabel: DepartmentLabel,
): ProgressStep[] {
  const resolved = ahead('Resolved', 'pending', 'Pending');
  switch (ticket.status) {
    case 'new':
      return [ahead('Drafted', 'pending', 'Pending'), resolved];
    case 'processing': {
      const redraft = events.some((event) => event.event === 'drafted');
      return [ahead(redraft ? 'Redrafting the reply' : 'Drafting the reply', 'current', 'In progress'), resolved];
    }
    case 'escalated':
      return [
        ahead(`Waiting for ${departmentLabel(ticket.escalatedDept)}`, 'current', 'In progress'),
        resolved,
      ];
    case 'drafted':
    case 'needs_review':
    case 'dept_responded':
      return [ahead('Resolved', 'current', 'Review the draft, then send it')];
    case 'processing_failed':
      return [resolved];
    case 'resolved':
      return [];
  }
}

export function buildProgress(
  ticket: Ticket,
  events: readonly TicketEvent[],
  departmentLabel: DepartmentLabel,
): TicketProgress {
  const steps = milestones(events, departmentLabel);

  // The ticket row vouches for these two even when their event is missing.
  if (!events.some((event) => event.event === 'created')) {
    steps.unshift(done('received', 'Received', ticket.createdAt));
  }
  if (ticket.status === 'resolved' && !events.some((event) => event.event === 'resolved')) {
    steps.push(done('resolved', 'Resolved', ticket.resolvedAt));
  }

  return {
    steps: [...steps, ...stepsAhead(ticket, events, departmentLabel)],
    failed: ticket.status === 'processing_failed',
  };
}
