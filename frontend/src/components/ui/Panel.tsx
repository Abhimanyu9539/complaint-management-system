import type { ReactNode } from 'react';

interface PanelProps {
  title: string;
  /** Uppercase micro-label above the title — the prototype's sectioning device. */
  eyebrow?: string;
  description?: string;
  /** Right side of the header rail: a Select, a badge, a link. */
  actions?: ReactNode;
  /** Column span on the statistics grid. */
  span?: 1 | 2 | 3;
  /** Drops the body padding so a table can draw edge to edge. */
  flush?: boolean;
  children: ReactNode;
  className?: string;
}

// Complete literal classes — Tailwind's scanner cannot see an interpolated one.
const SPANS: Record<NonNullable<PanelProps['span']>, string> = {
  1: '',
  2: 'lg:col-span-2',
  3: 'lg:col-span-2 xl:col-span-3',
};

/**
 * The card every admin section sits in.
 *
 * One elevation token, applied only here — everything else in the panel
 * separates with a border, so `shadow-card` continues to mean "this is a
 * distinct thing" rather than becoming ambient decoration.
 */
export function Panel({
  title,
  eyebrow,
  description,
  actions,
  span = 1,
  flush = false,
  children,
  className = '',
}: PanelProps) {
  return (
    <section
      className={`flex min-w-0 flex-col rounded-xl border border-border bg-surface shadow-card ${SPANS[span]} ${className}`}
    >
      <header className="flex min-h-13 shrink-0 items-start justify-between gap-3 px-4 py-3">
        <div className="min-w-0">
          {eyebrow && (
            <p className="mb-0.5 text-[10px] font-semibold tracking-[0.08em] text-text-faint uppercase">
              {eyebrow}
            </p>
          )}
          <h2 className="truncate text-[13px] font-semibold text-text">{title}</h2>
          {description && <p className="mt-1 text-[12px] text-text-muted">{description}</p>}
        </div>
        {actions && <div className="flex shrink-0 items-center gap-2">{actions}</div>}
      </header>

      <div className={flush ? 'min-w-0 flex-1' : 'min-w-0 flex-1 px-4 pt-1 pb-4'}>{children}</div>
    </section>
  );
}
