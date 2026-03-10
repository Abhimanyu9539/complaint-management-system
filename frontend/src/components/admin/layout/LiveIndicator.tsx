import { Pause, Play, RotateCw } from 'lucide-react';
import { ICON_SIZE, IconButton } from '@/components/ui/IconButton';
import { useNow } from '@/hooks/useNow';
import { formatRelativeTime } from '@/lib/format';
import { useAdminRefresh } from '@/state/AdminRefreshProvider';

/**
 * Freshness readout plus the pause and refresh controls.
 *
 * The timestamp shown is the *oldest* of every panel's last successful load,
 * not the newest. Reporting the newest would let one fast-refreshing panel
 * vouch for a stale one sitting beside it — on an ops screen, the pessimistic
 * number is the only honest one.
 */
export function LiveIndicator() {
  const { paused, togglePause, refreshAll, readOldestUpdate, intervalMs } = useAdminRefresh();
  // Re-renders on its own slow tick so "14s ago" keeps counting without the
  // panels re-rendering.
  const now = useNow(5000);
  const oldest = readOldestUpdate();

  return (
    <div className="flex shrink-0 items-center gap-1">
      <span className="hidden text-[11px] text-text-faint tabular-nums sm:inline">
        {paused ? 'Paused' : oldest ? `Updated ${formatRelativeTime(oldest, now)}` : 'Loading…'}
      </span>
      <IconButton
        onClick={togglePause}
        aria-label={paused ? 'Resume auto-refresh' : 'Pause auto-refresh'}
        title={
          paused
            ? 'Resume auto-refresh'
            : `Pause auto-refresh (currently every ${Math.round(intervalMs / 1000)}s)`
        }
      >
        {paused ? (
          <Play size={ICON_SIZE - 2} strokeWidth={1.75} />
        ) : (
          <Pause size={ICON_SIZE - 2} strokeWidth={1.75} />
        )}
      </IconButton>
      <IconButton onClick={refreshAll} aria-label="Refresh now" title="Refresh now">
        <RotateCw size={ICON_SIZE - 2} strokeWidth={1.75} />
      </IconButton>
    </div>
  );
}
