/**
 * A loading placeholder.
 *
 * The pulse is suppressed under `prefers-reduced-motion` by the global rule in
 * index.css, so this stays a plain block for users who asked for that.
 */
export function Skeleton({ className = '' }: { className?: string }) {
  return (
    <div
      aria-hidden="true"
      className={`rounded bg-surface-2 ${className}`}
      style={{ animation: 'pulse-soft 1.8s ease-in-out infinite' }}
    />
  );
}

/**
 * Ragged widths, deliberately: equal-length bars read as a table and set the
 * wrong expectation for the text that is about to replace them.
 */
const LINE_WIDTHS = ['w-full', 'w-11/12', 'w-4/5', 'w-full', 'w-3/4', 'w-5/6'];

/** A stack of lines, for text-shaped loading regions. */
export function SkeletonLines({ rows = 3, className = '' }: { rows?: number; className?: string }) {
  return (
    <div className={`flex flex-col gap-2 ${className}`}>
      {Array.from({ length: rows }, (_, index) => (
        <Skeleton key={index} className={`h-3.5 ${LINE_WIDTHS[index % LINE_WIDTHS.length]}`} />
      ))}
    </div>
  );
}
