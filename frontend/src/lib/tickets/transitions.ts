/**
 * The two edges of `ticket_service.ALLOWED` (lld.md §2) the UI can drive.
 *
 * Mirrored from the backend so a button disables instead of offering an action
 * that will come back 409. The backend is still the authority — this is the
 * difference between a refusal the operator saw coming and one that looks like
 * a bug. Kept in one place so `/admin/tickets` and the workbench cannot drift
 * onto two different mirrors of the same table.
 */

import type { TicketStatus } from './types';

const CAN_ESCALATE = new Set<TicketStatus>(['new', 'drafted', 'needs_review', 'dept_responded']);
const CAN_RESOLVE = new Set<TicketStatus>([
  'new',
  'drafted',
  'needs_review',
  'escalated',
  'dept_responded',
]);

export function canEscalate(status: TicketStatus): boolean {
  return CAN_ESCALATE.has(status);
}

export function canResolve(status: TicketStatus): boolean {
  return CAN_RESOLVE.has(status);
}

/** True once a ticket can no longer be escalated or resolved from here. */
export function hasNoActions(status: TicketStatus): boolean {
  return !canEscalate(status) && !canResolve(status);
}
