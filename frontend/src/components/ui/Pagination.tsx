import { ChevronLeft, ChevronRight } from 'lucide-react';
import { IconButton } from './IconButton';

interface PaginationProps {
  total: number;
  limit: number;
  offset: number;
  onChange(offset: number): void;
  className?: string;
}

export function Pagination({ total, limit, offset, onChange, className = '' }: PaginationProps) {
  // Nothing to page through — rendering disabled arrows over "0–0 of 0" is
  // noise the empty state has already covered.
  if (total <= limit) return null;

  const first = offset + 1;
  const last = Math.min(offset + limit, total);
  const canGoBack = offset > 0;
  const canGoForward = offset + limit < total;

  return (
    <div className={`flex items-center justify-between gap-3 px-4 py-2.5 ${className}`}>
      <p className="text-[11px] text-text-muted tabular-nums">
        {first.toLocaleString()}–{last.toLocaleString()} of {total.toLocaleString()}
      </p>
      <div className="flex items-center gap-1">
        <IconButton
          onClick={() => onChange(Math.max(0, offset - limit))}
          disabled={!canGoBack}
          aria-label="Previous page"
          title="Previous page"
          className="disabled:cursor-not-allowed disabled:opacity-40"
        >
          <ChevronLeft size={15} strokeWidth={1.75} />
        </IconButton>
        <IconButton
          onClick={() => onChange(offset + limit)}
          disabled={!canGoForward}
          aria-label="Next page"
          title="Next page"
          className="disabled:cursor-not-allowed disabled:opacity-40"
        >
          <ChevronRight size={15} strokeWidth={1.75} />
        </IconButton>
      </div>
    </div>
  );
}
