import type { ReactNode } from 'react';
import type { AsyncStatus } from '@/hooks/useAsyncData';
import { ErrorState } from './ErrorState';
import { InlineError } from './InlineError';

interface AsyncBoundaryProps {
  status: AsyncStatus;
  error: string | null;
  errorDetail?: string | null;
  failureCount?: number;
  /** Whether the loaded payload has nothing worth rendering. */
  isEmpty: boolean;
  empty: ReactNode;
  skeleton: ReactNode;
  onRetry?(): void;
  children: ReactNode;
}

/**
 * One place that decides what a panel shows for every combination of load state
 * and data presence. Getting this consistent across a dozen panels by hand is
 * how dashboards end up flickering between spinners and blank cards.
 *
 * | status       | isEmpty | renders                          |
 * |--------------|---------|----------------------------------|
 * | loading      | —       | skeleton                         |
 * | refreshing   | —       | children (stale data stays put)  |
 * | success      | true    | empty                            |
 * | success      | false   | children                         |
 * | error        | true    | ErrorState with a retry          |
 * | error        | false   | InlineError above children       |
 *
 * The last row is the important one: a failed *refresh* must not discard data
 * that loaded successfully a minute ago.
 */
export function AsyncBoundary({
  status,
  error,
  errorDetail,
  failureCount = 0,
  isEmpty,
  empty,
  skeleton,
  onRetry,
  children,
}: AsyncBoundaryProps) {
  if (status === 'loading') return <>{skeleton}</>;

  if (status === 'error') {
    if (isEmpty) {
      return (
        <ErrorState
          message={error ?? 'Something went wrong.'}
          detail={errorDetail}
          onRetry={onRetry}
        />
      );
    }
    return (
      <div className="flex min-w-0 flex-col gap-3">
        <InlineError
          message={error ?? 'Refresh failed — showing the last known values.'}
          failureCount={failureCount}
          onRetry={onRetry}
        />
        {children}
      </div>
    );
  }

  // `refreshing` deliberately falls through to children: the header spinner is
  // the only signal a background poll is in flight.
  if (status === 'success' && isEmpty) return <>{empty}</>;

  return <>{children}</>;
}
