/**
 * The admin transport's error type.
 *
 * Its own module because both transports throw it and `realTransport` already
 * imports `mockTransport` (it spreads the mock and overrides the served
 * methods). Declaring the class in either one would close that into an import
 * cycle, and a cycle through a `class` declaration is the kind that bites at
 * runtime: the binding is hoisted but uninitialised, so whichever module the
 * bundler evaluates second throws a temporal-dead-zone error on first use —
 * inside a `catch`, where it would be reported as the original failure.
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
