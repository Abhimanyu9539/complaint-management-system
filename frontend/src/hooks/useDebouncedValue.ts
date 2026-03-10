import { useEffect, useState } from 'react';

/**
 * Trails `value` by `delayMs`, so a search box does not fire a request per
 * keystroke. Used by `SearchInput`, which owns the debounce on behalf of every
 * page rather than each page repeating it.
 */
export function useDebouncedValue<T>(value: T, delayMs = 300): T {
  const [debounced, setDebounced] = useState(value);

  useEffect(() => {
    const timer = setTimeout(() => setDebounced(value), delayMs);
    return () => clearTimeout(timer);
  }, [value, delayMs]);

  return debounced;
}
