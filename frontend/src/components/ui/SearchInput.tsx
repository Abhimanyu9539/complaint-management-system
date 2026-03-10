import { Search, X } from 'lucide-react';
import { useEffect, useId, useRef, useState } from 'react';
import { useDebouncedValue } from '@/hooks/useDebouncedValue';

interface SearchInputProps {
  value: string;
  onChange(value: string): void;
  placeholder?: string;
  label?: string;
  debounceMs?: number;
  className?: string;
}

/**
 * A debounced search box.
 *
 * The debounce lives here rather than in each page so no page can forget it and
 * fire a request per keystroke. The input keeps its own immediate state so
 * typing stays responsive while the committed value trails behind.
 */
export function SearchInput({
  value,
  onChange,
  placeholder = 'Search…',
  label = 'Search',
  debounceMs = 300,
  className = '',
}: SearchInputProps) {
  const id = useId();
  const [draft, setDraft] = useState(value);
  const debounced = useDebouncedValue(draft, debounceMs);
  const onChangeRef = useRef(onChange);
  onChangeRef.current = onChange;

  // Publish upward when the debounced value settles. Guarded against
  // re-emitting the value we were handed, which would loop with a URL-backed
  // parent that re-renders on every commit.
  useEffect(() => {
    if (debounced !== value) onChangeRef.current(debounced);
    // `value` is deliberately excluded: including it would re-fire this effect
    // when the parent echoes our own change back, cancelling the next keystroke.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [debounced]);

  // Adopt an externally-driven change (back button, cleared filters) without
  // clobbering what the user is mid-way through typing.
  useEffect(() => {
    if (value !== debounced) setDraft(value);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [value]);

  return (
    <div className={`flex min-w-0 flex-col gap-1 ${className}`}>
      <label htmlFor={id} className="sr-only">
        {label}
      </label>
      <div className="relative">
        <Search
          size={14}
          strokeWidth={1.75}
          aria-hidden="true"
          className="pointer-events-none absolute top-1/2 left-2.5 -translate-y-1/2 text-text-faint"
        />
        <input
          id={id}
          type="search"
          value={draft}
          placeholder={placeholder}
          onChange={(event) => setDraft(event.target.value)}
          className="h-8 w-full rounded-lg border border-border bg-bg-elevated pr-8 pl-8 text-[12px] text-text transition-colors placeholder:text-text-faint hover:border-border-strong"
        />
        {draft && (
          <button
            type="button"
            onClick={() => setDraft('')}
            aria-label="Clear search"
            className="absolute top-1/2 right-2 -translate-y-1/2 rounded text-text-faint transition-colors hover:text-text"
          >
            <X size={13} strokeWidth={2} />
          </button>
        )}
      </div>
    </div>
  );
}
