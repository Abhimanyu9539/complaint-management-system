import {
  createContext,
  useCallback,
  useContext,
  useMemo,
  useRef,
  useState,
  type ReactNode,
} from 'react';

/**
 * Shared polling policy for the admin panel.
 *
 * Every panel fetches independently — one failing endpoint must not blank the
 * page — but they share a cadence, a pause switch and a "refresh everything"
 * button. That coordination lives here rather than in each page.
 */

const PAUSE_KEY = 'cms.admin.paused';
const DEFAULT_INTERVAL_MS = 20_000;

function readStoredPaused(): boolean {
  try {
    return localStorage.getItem(PAUSE_KEY) === 'true';
  } catch {
    // storage unavailable — polling just starts un-paused every load
    return false;
  }
}

function readInterval(): number {
  const raw = import.meta.env.VITE_ADMIN_POLL_MS;
  const parsed = raw ? Number.parseInt(raw, 10) : NaN;
  // A sub-second cadence would hammer Qdrant on every tick; the floor is not
  // negotiable even if someone sets the env var to 100.
  return Number.isFinite(parsed) && parsed >= 2000 ? parsed : DEFAULT_INTERVAL_MS;
}

interface AdminRefreshContextValue {
  /** Base cadence in ms. Panels multiply it — health 3×, storage 2×. */
  intervalMs: number;
  paused: boolean;
  togglePause(): void;
  /**
   * Monotonic counter. Every panel includes it in its `deps`, so bumping it
   * refetches the whole page at once.
   */
  refreshToken: number;
  refreshAll(): void;
  /** Panels report their last successful load here. */
  reportUpdate(panelId: string, iso: string | null): void;
  /** Oldest reported timestamp — the honest thing for the header to display. */
  readOldestUpdate(): string | null;
}

const AdminRefreshContext = createContext<AdminRefreshContextValue | null>(null);

export function AdminRefreshProvider({ children }: { children: ReactNode }) {
  const [paused, setPaused] = useState(readStoredPaused);
  const [refreshToken, setRefreshToken] = useState(0);
  const intervalMs = useMemo(readInterval, []);

  /**
   * Panel timestamps live in a ref, not state.
   *
   * Eight panels each reporting a new timestamp per poll would trigger eight
   * re-renders of the whole page every cadence. The header re-reads this on its
   * own slow tick instead, so the freshness display costs nothing.
   */
  const updatesRef = useRef(new Map<string, string | null>());

  const togglePause = useCallback(() => {
    setPaused((current) => {
      const next = !current;
      try {
        localStorage.setItem(PAUSE_KEY, String(next));
      } catch {
        // storage unavailable — the pause just won't persist across reloads
      }
      return next;
    });
  }, []);

  const refreshAll = useCallback(() => {
    setRefreshToken((token) => token + 1);
  }, []);

  const reportUpdate = useCallback((panelId: string, iso: string | null) => {
    updatesRef.current.set(panelId, iso);
  }, []);

  const readOldestUpdate = useCallback((): string | null => {
    let oldest: string | null = null;
    for (const iso of updatesRef.current.values()) {
      // A panel that has never loaded reports null. Ignoring it would let the
      // header claim the page is fresh while one panel is still empty, so the
      // oldest-wins rule only considers panels that have actually reported.
      if (!iso) continue;
      if (oldest === null || iso < oldest) oldest = iso;
    }
    return oldest;
  }, []);

  const value = useMemo<AdminRefreshContextValue>(
    () => ({
      intervalMs,
      paused,
      togglePause,
      refreshToken,
      refreshAll,
      reportUpdate,
      readOldestUpdate,
    }),
    [intervalMs, paused, togglePause, refreshToken, refreshAll, reportUpdate, readOldestUpdate],
  );

  return <AdminRefreshContext.Provider value={value}>{children}</AdminRefreshContext.Provider>;
}

export function useAdminRefresh(): AdminRefreshContextValue {
  const ctx = useContext(AdminRefreshContext);
  if (!ctx) throw new Error('useAdminRefresh must be used within an AdminRefreshProvider');
  return ctx;
}
