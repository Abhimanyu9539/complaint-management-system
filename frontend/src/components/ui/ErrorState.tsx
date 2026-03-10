import { RotateCw, TriangleAlert } from 'lucide-react';
import { Button } from './Button';

interface ErrorStateProps {
  title?: string;
  message: string;
  /** Raw technical detail, kept in a collapsed disclosure rather than hidden. */
  detail?: string | null;
  onRetry?(): void;
  className?: string;
}

/**
 * A failed load with nothing to fall back on.
 *
 * When there *is* retained data from an earlier successful poll, use
 * `InlineError` instead — showing this full-panel state would throw away
 * numbers that are still useful just because the latest refresh failed.
 */
export function ErrorState({ title = 'Could not load this', message, detail, onRetry, className = '' }: ErrorStateProps) {
  return (
    <div
      className={`flex flex-col items-center justify-center gap-2 px-6 py-10 text-center ${className}`}
    >
      <TriangleAlert size={18} strokeWidth={1.75} className="text-danger" />
      <p className="text-[13px] font-medium text-text">{title}</p>
      <p className="max-w-sm text-[12px] leading-relaxed text-text-muted">{message}</p>

      {detail && (
        <details className="mt-1 max-w-full text-left">
          <summary className="cursor-pointer text-[11px] text-text-faint hover:text-text-muted">
            Technical detail
          </summary>
          <pre className="mt-1.5 max-w-full overflow-x-auto rounded-lg border border-border bg-surface-2 p-2 font-mono text-[11px] whitespace-pre-wrap text-text-muted">
            {detail}
          </pre>
        </details>
      )}

      {onRetry && (
        <Button
          size="sm"
          onClick={onRetry}
          icon={<RotateCw size={13} strokeWidth={1.75} />}
          className="mt-1"
        >
          Try again
        </Button>
      )}
    </div>
  );
}
