import { useEffect } from 'react';
import { useAsyncData, type AsyncData } from '@/hooks/useAsyncData';
import { useAdminRefresh } from '@/state/AdminRefreshProvider';
import type { AdminResult } from '@/lib/admin/types';

interface UsePanelDataOptions {
  /**
   * Multiplies the shared base cadence. Health checks make outbound HTTP calls
   * and Qdrant reads are the slowest thing in the panel, so those poll at 3×
   * and 2× rather than getting their own hardcoded intervals.
   */
  intervalFactor?: number;
  /** Extra values that identify the request — filters, page, day range. */
  deps?: readonly unknown[];
  /** Fetch once instead of polling. Drawers and pickers do not need a cadence. */
  once?: boolean;
  enabled?: boolean;
}

/**
 * `useAsyncData` wired into the panel-wide refresh policy.
 *
 * Every admin panel needs the same four things: the shared cadence, the pause
 * switch, the page-wide refresh token in its deps, and a report of its last
 * successful load so the header can show the honest oldest-update time. Doing
 * that inline in a dozen panels is a dozen chances to forget one.
 */
export function usePanelData<T>(
  panelId: string,
  fetcher: (signal: AbortSignal) => Promise<AdminResult<T>>,
  options: UsePanelDataOptions = {},
): AsyncData<T> {
  const { intervalFactor = 1, deps = [], once = false, enabled = true } = options;
  const { intervalMs, paused, refreshToken, reportUpdate } = useAdminRefresh();

  const state = useAsyncData(fetcher, {
    intervalMs: once ? 0 : intervalMs * intervalFactor,
    // `refreshToken` in deps is what makes the header's refresh button refetch
    // every panel at once rather than only the one that owns the button.
    deps: [refreshToken, ...deps],
    enabled: enabled && !paused,
  });

  useEffect(() => {
    reportUpdate(panelId, state.updatedAt);
    // Unregister on unmount, or a page the user has navigated away from keeps
    // dragging the header's "oldest update" backwards forever.
    return () => reportUpdate(panelId, null);
  }, [panelId, state.updatedAt, reportUpdate]);

  return state;
}
