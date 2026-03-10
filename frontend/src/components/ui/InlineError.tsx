import { RotateCw, TriangleAlert } from 'lucide-react';
import { IconButton } from './IconButton';

interface InlineErrorProps {
  message: string;
  /** Consecutive failures. Shown once it is more than a blip. */
  failureCount?: number;
  onRetry?(): void;
  className?: string;
}

/**
 * A one-line failure strip shown *above retained data*.
 *
 * This is the component that makes error retention visible. When a background
 * refresh fails, the panel keeps rendering the last good numbers and puts this
 * on top, so the operator sees both "here is what we last knew" and "this is no
 * longer being updated" — rather than either a blanked panel or, worse, stale
 * numbers presented as current.
 */
export function InlineError({ message, failureCount = 0, onRetry, className = '' }: InlineErrorProps) {
  return (
    <div
      role="status"
      className={`flex items-center gap-2 rounded-lg border border-danger/30 bg-danger-soft px-3 py-1.5 text-[12px] text-danger ${className}`}
    >
      <TriangleAlert size={13} strokeWidth={2} className="shrink-0" />
      <span className="min-w-0 flex-1 truncate">
        {message}
        {failureCount > 1 && (
          <span className="ml-1 tabular-nums opacity-80">({failureCount} attempts)</span>
        )}
      </span>
      {onRetry && (
        <IconButton onClick={onRetry} aria-label="Retry" title="Retry" className="h-6 w-6">
          <RotateCw size={12} strokeWidth={2} />
        </IconButton>
      )}
    </div>
  );
}
