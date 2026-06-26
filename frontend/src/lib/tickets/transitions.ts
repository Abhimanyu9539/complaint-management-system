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

// The draft is read-only while a department owns the ticket, and once it is closed.
// Mirrors `reply_service.DRAFT_LOCKED_STATUSES`.
const DRAFT_LOCKED = new Set<TicketStatus>(['escalated', 'resolved']);

/** True when the draft can't be edited, discarded or sent. */
export function isDraftLocked(status: TicketStatus): boolean {
  return DRAFT_LOCKED.has(status);
}

/** Sending the reply resolves the ticket, so it needs resolving to be allowed — and an unlocked draft. */
export function canSend(status: TicketStatus): boolean {
  return canResolve(status) && !isDraftLocked(status);
}

const CAN_REGENERATE = new Set<TicketStatus>([
  'new',
  'drafted',
  'needs_review',
  'dept_responded',
  'processing_failed',
]);

/** Where the backend lets the ticket graph run again (`ticket_service.ALLOWED` → `processing`). */
export function canRegenerate(status: TicketStatus): boolean {
  return CAN_REGENERATE.has(status);
}

/** The department's answer can be recorded only while the ticket waits for it. */
export function canRecordDeptResponse(status: TicketStatus): boolean {
  return status === 'escalated';
}

/** True once a ticket can no longer be escalated or resolved from here. */
export function hasNoActions(status: TicketStatus): boolean {
  return !canEscalate(status) && !canResolve(status);
}
