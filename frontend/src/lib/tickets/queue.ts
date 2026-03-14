/**
 * Grouping the ticket queue by status, for the workbench.
 *
 * A dedicated module rather than inline in the component: oxlint's
 * `react/only-export-components` forbids a component file from exporting
 * helper functions, and this grouping is also what the `J`/`K` keyboard
 * navigation walks, so both the renderer and the keyboard handler need the
 * same order.
 */

import type { Ticket, TicketStatus } from './types';

/**
 * Triage order: a ticket a department has replied to needs a human first —
 * someone is waiting on *us* now. Needing review and brand-new come next,
 * then the paths already moving on their own, then terminal states last.
 */
export const QUEUE_GROUP_ORDER: readonly TicketStatus[] = [
  'dept_responded',
  'needs_review',
  'new',
  'processing',
  'drafted',
  'escalated',
  'resolved',
  'processing_failed',
];

export interface TicketGroup {
  status: TicketStatus;
  tickets: Ticket[];
}

/**
 * Every status in `QUEUE_GROUP_ORDER` gets a group, even at zero — an absent
 * section is ambiguous between "nothing here" and "not tracked", the same
 * reasoning `admin_stats.py` applies to a missing department bar.
 */
export function groupTicketsByStatus(tickets: readonly Ticket[]): TicketGroup[] {
  return QUEUE_GROUP_ORDER.map((status) => ({
    status,
    tickets: tickets.filter((ticket) => ticket.status === status),
  }));
}

/** Flattened in the same order the groups render — the sequence `J`/`K` walks. */
export function flattenQueueOrder(tickets: readonly Ticket[]): Ticket[] {
  return groupTicketsByStatus(tickets).flatMap((group) => group.tickets);
}
