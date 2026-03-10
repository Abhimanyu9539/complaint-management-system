import { useCallback, useMemo } from 'react';
import { useSearchParams } from 'react-router';

/**
 * Reads and writes one URL query parameter as component state.
 *
 * Filters live in the URL rather than in component state so a filtered view is
 * shareable, survives a reload, and steps correctly under the back button —
 * which is the whole reason the admin panel got a router.
 *
 * A value equal to `fallback` is removed from the URL rather than written, so
 * the default view has a clean address instead of `?status=all&type=all&page=1`.
 */
export function useQueryParamState(
  key: string,
  fallback: string,
): [string, (next: string) => void] {
  const [searchParams, setSearchParams] = useSearchParams();
  const value = searchParams.get(key) ?? fallback;

  const setValue = useCallback(
    (next: string) => {
      setSearchParams(
        (current) => {
          const params = new URLSearchParams(current);
          if (next === fallback || next === '') {
            params.delete(key);
          } else {
            params.set(key, next);
          }
          // Changing a filter invalidates the current page — staying on page 4
          // of a narrower result set usually lands on an empty table, which
          // reads as "no results" rather than "wrong page".
          if (key !== 'page') params.delete('page');
          return params;
        },
        // Filter changes replace rather than push: otherwise typing a six-letter
        // search term buries the previous page under six history entries.
        { replace: true },
      );
    },
    [fallback, key, setSearchParams],
  );

  return [value, setValue];
}

/** The same, parsed as a positive integer — page numbers and day ranges. */
export function useQueryParamNumber(
  key: string,
  fallback: number,
): [number, (next: number) => void] {
  const [raw, setRaw] = useQueryParamState(key, String(fallback));

  const value = useMemo(() => {
    const parsed = Number.parseInt(raw, 10);
    return Number.isFinite(parsed) && parsed > 0 ? parsed : fallback;
  }, [raw, fallback]);

  const setValue = useCallback((next: number) => setRaw(String(next)), [setRaw]);

  return [value, setValue];
}
