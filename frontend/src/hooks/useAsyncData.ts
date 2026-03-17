import { useCallback, useEffect, useRef, useState } from 'react';
import type { AdminResult } from '@/lib/admin/types';

/**
 * Fetching, polling and error retention for every admin panel.
 *
 * There is no query library in this project, and adding one for a single
 * feature would be a large dependency for a small surface. This hook is the
 * minimum that makes a polled ops dashboard trustworthy.
 */

export type AsyncStatus = 'loading' | 'refreshing' | 'success' | 'error';

export interface AsyncData<T> {
  /**
   * Retained across a failed refresh. A dashboard that blanks out on one bad
   * poll is worse than one showing slightly stale numbers with a warning.
   */
  data: T | null;
  status: AsyncStatus;
  error: string | null;
  /** Extra context for the error, shown in a collapsed disclosure. */
  errorDetail: string | null;
  /** ISO time of the last *successful* load. Drives "Updated 14s ago". */
  updatedAt: string | null;
  /** Consecutive failures. Also drives the backoff multiplier. */
  failureCount: number;
  refresh(): void;
}

interface UseAsyncDataOptions {
  /** Poll cadence in ms. Omit or pass 0 to fetch once. */
  intervalMs?: number;
  /**
   * Values that identify the request. Any change refetches from `loading`
   * rather than `refreshing`, because a filter change is a new question, not a
   * refresh of the old one — the user should see a skeleton, not stale rows.
   */
  deps?: readonly unknown[];
  /** Skips fetching entirely: a paused dashboard, or an unopened drawer. */
  enabled?: boolean;
  /** Cap on the consecutive-failure backoff multiplier. */
  maxBackoff?: number;
}

function messageOf(err: unknown): { message: string; detail: string | null } {
  if (err instanceof Error) {
    const detail = 'detail' in err ? ((err as { detail?: unknown }).detail ?? null) : null;
    return { message: err.message, detail: detail === null ? null : String(detail) };
  }
  return { message: 'Something went wrong loading this.', detail: null };
}

export function useAsyncData<T>(
  fetcher: (signal: AbortSignal) => Promise<AdminResult<T>>,
  options: UseAsyncDataOptions = {},
): AsyncData<T> {
  const { intervalMs = 0, deps = [], enabled = true, maxBackoff = 4 } = options;

  const [data, setData] = useState<T | null>(null);
  const [status, setStatus] = useState<AsyncStatus>('loading');
  const [error, setError] = useState<string | null>(null);
  const [errorDetail, setErrorDetail] = useState<string | null>(null);
  const [updatedAt, setUpdatedAt] = useState<string | null>(null);
  const [failureCount, setFailureCount] = useState(0);
  const [refreshTick, setRefreshTick] = useState(0);

  /**
   * Every call site passes an inline arrow, so `fetcher` has a new identity on
   * every render. Putting it in the effect's dependency array would refetch on
   * every render — an infinite loop. It lives in a ref instead, and `deps` is
   * the explicit "this is a different request now" key. That is the entire
   * reason `deps` exists.
   */
  const fetcherRef = useRef(fetcher);
  fetcherRef.current = fetcher;

  const abortRef = useRef<AbortController | null>(null);
  const timerRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  /** Serialised deps of the last completed load, to tell first load from refresh. */
  const loadedKeyRef = useRef<string | null>(null);
  const failureCountRef = useRef(0);

  const depsKey = JSON.stringify(deps);

  const refresh = useCallback(() => {
    setRefreshTick((tick) => tick + 1);
  }, []);

  useEffect(() => {
    if (!enabled) {
      // A disabled panel must not hold an in-flight request open; the next
      // enable starts clean.
      abortRef.current?.abort();
      if (timerRef.current) clearTimeout(timerRef.current);
      return;
    }

    let cancelled = false;

    const run = async () => {
      abortRef.current?.abort();
      const controller = new AbortController();
      abortRef.current = controller;

      // A first load of this deps key shows a skeleton; every later tick keeps
      // the existing rows on screen and only spins the header.
      const isFirstLoad = loadedKeyRef.current !== depsKey;
      setStatus(isFirstLoad ? 'loading' : 'refreshing');

      try {
        const result = await fetcherRef.current(controller.signal);
        if (cancelled || controller.signal.aborted) return;

        setData(result.data);
        setUpdatedAt(result.fetchedAt);
        setError(null);
        setErrorDetail(null);
        setStatus('success');
        failureCountRef.current = 0;
        setFailureCount(0);
        loadedKeyRef.current = depsKey;
      } catch (err) {
        // Must come before any setState: React 19 StrictMode double-mounts every
        // effect, so the first controller is always aborted, and without this
        // guard every panel would flash an error on its first paint.
        if (err instanceof DOMException && err.name === 'AbortError') return;
        if (cancelled) return;

        const { message, detail } = messageOf(err);
        setError(message);
        setErrorDetail(detail);
        setStatus('error');
        failureCountRef.current += 1;
        setFailureCount(failureCountRef.current);
        // `data` and `updatedAt` are deliberately left alone — see AsyncData.
      } finally {
        // Written as a positive condition rather than an early `return`: a
        // `return` inside `finally` overwrites the control flow of the `catch`
        // above it, which is confusing to read even where it is harmless.
        if (!cancelled && intervalMs > 0) {
          // setTimeout re-armed after each settle, never setInterval: a backend
          // slower than the cadence would otherwise stack overlapping requests
          // until it collapsed under them.
          const backoff = Math.min(2 ** failureCountRef.current, maxBackoff);
          timerRef.current = setTimeout(run, intervalMs * backoff);
        }
      }
    };

    void run();

    return () => {
      cancelled = true;
      abortRef.current?.abort();
      if (timerRef.current) clearTimeout(timerRef.current);
    };
    // `fetcher` is intentionally absent — see the fetcherRef comment above.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [depsKey, enabled, intervalMs, maxBackoff, refreshTick]);

  /**
   * A backgrounded tab must cost nothing. On hide, drop the pending timer and
   * abort anything in flight; on show, fetch immediately rather than waiting
   * out the remainder of an interval that elapsed while nobody was looking.
   */
  useEffect(() => {
    if (!enabled || intervalMs <= 0) return;

    const onVisibilityChange = () => {
      if (document.visibilityState === 'hidden') {
        if (timerRef.current) clearTimeout(timerRef.current);
        abortRef.current?.abort();
      } else {
        setRefreshTick((tick) => tick + 1);
      }
    };

    document.addEventListener('visibilitychange', onVisibilityChange);
    return () => document.removeEventListener('visibilitychange', onVisibilityChange);
  }, [enabled, intervalMs]);

  return {
    data,
    status,
    error,
    errorDetail,
    updatedAt,
    failureCount,
    refresh,
  };
}
