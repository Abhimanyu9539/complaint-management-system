import type { ReactNode } from 'react';

interface EmptyStateProps {
  icon?: ReactNode;
  title: string;
  /**
   * What to do about it. Empty states in an ops panel should be instructive —
   * "No ingestion jobs yet" is a dead end; "Run `uv run cms-seed`" is not.
   */
  description?: ReactNode;
  action?: ReactNode;
  className?: string;
}

export function EmptyState({ icon, title, description, action, className = '' }: EmptyStateProps) {
  return (
    <div
      className={`flex flex-col items-center justify-center gap-2 px-6 py-10 text-center ${className}`}
    >
      {icon && <div className="text-text-faint">{icon}</div>}
      <p className="text-[13px] font-medium text-text">{title}</p>
      {description && (
        <div className="max-w-sm text-[12px] leading-relaxed text-text-muted">{description}</div>
      )}
      {action && <div className="mt-1">{action}</div>}
    </div>
  );
}

/**
 * Inline monospace for a shell command inside an empty state's description.
 * Exported here rather than in `lib/` because it is a component, and oxlint's
 * only-export-components rule is satisfied by that.
 */
export function CommandHint({ children }: { children: ReactNode }) {
  return (
    <code className="rounded border border-border bg-surface-2 px-1.5 py-0.5 font-mono text-[11px] text-text">
      {children}
    </code>
  );
}
