import { useEffect, useState } from 'react';

/**
 * A clock that ticks on an interval, for relative timestamps.
 *
 * "Updated 14s ago" has to keep counting while the data itself is unchanged, so
 * something has to re-render independently of the fetch. Isolating that in a
 * hook means only the small components that display an age re-render on the
 * tick, rather than the panel that owns the data.
 */
export function useNow(intervalMs = 10_000): number {
  const [now, setNow] = useState(() => Date.now());

  useEffect(() => {
    const timer = setInterval(() => setNow(Date.now()), intervalMs);
    return () => clearInterval(timer);
  }, [intervalMs]);

  return now;
}
