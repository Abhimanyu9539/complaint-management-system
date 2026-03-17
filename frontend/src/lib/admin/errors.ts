/**
 * The admin transport's error type. Its own module so both `realTransport.ts`
 * and callers like `hooks/useTicketActions.ts` can import it without pulling
 * in the whole transport.
 */

/**
 * Thrown for every non-abort failure. `useAsyncData` turns it into UI state.
 *
 * Deliberately unlike `lib/chat`, which swallows failures and returns an empty
 * list. An empty session list is a harmless degraded state; an admin dashboard
 * silently showing zeros during an outage is not. "0 documents indexed" and "we
 * could not reach the API" must never look the same.
 */
export class AdminRequestError extends Error {
  readonly status: number | null;
  readonly detail?: string;

  constructor(message: string, status: number | null, detail?: string) {
    super(message);
    this.name = 'AdminRequestError';
    this.status = status;
    this.detail = detail;
  }
}
