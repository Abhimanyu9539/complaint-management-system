interface Segment {
  key: string;
  label: string;
  value: number;
  /** A Tailwind background utility, e.g. `bg-ok`. Complete literal, never interpolated. */
  className: string;
}

interface StackedBarProps {
  segments: Segment[];
  /** Renders a legend row with counts underneath. */
  showLegend?: boolean;
  height?: number;
  className?: string;
}

/**
 * A single horizontal proportion bar — HTML, deliberately not SVG.
 *
 * A flex row of percentage-width divs is responsive with no measurement, needs
 * no scale math, and carries its own accessible name. Reaching for SVG here
 * would be worse in every dimension.
 *
 * There is no donut chart anywhere in this panel for a related reason: comparing
 * angles is harder than comparing lengths, and a four-way status split is
 * exactly the case where that difference bites.
 */
export function StackedBar({
  segments,
  showLegend = true,
  height = 10,
  className = '',
}: StackedBarProps) {
  const total = segments.reduce((sum, segment) => sum + segment.value, 0);
  const present = segments.filter((segment) => segment.value > 0);

  const summary = present.map((segment) => `${segment.value} ${segment.label}`).join(', ');

  return (
    <div className={`flex min-w-0 flex-col gap-2 ${className}`}>
      <div
        role="img"
        aria-label={total === 0 ? 'No documents' : summary}
        className="flex w-full overflow-hidden rounded-full bg-surface-2"
        style={{ height }}
      >
        {present.map((segment) => (
          <div
            key={segment.key}
            className={segment.className}
            style={{ width: `${(segment.value / total) * 100}%` }}
            title={`${segment.label}: ${segment.value}`}
          />
        ))}
      </div>

      {showLegend && (
        <ul className="flex flex-wrap items-center gap-x-3 gap-y-1">
          {/* Every segment is listed, including zero-valued ones. "0 failed" is
              information; an absent row leaves the reader unsure whether the
              category was empty or simply not tracked. */}
          {segments.map((segment) => (
            <li key={segment.key} className="flex items-center gap-1.5 text-[11px]">
              <span
                aria-hidden="true"
                className={`h-2 w-2 shrink-0 rounded-full ${segment.value === 0 ? 'bg-border-strong' : segment.className}`}
              />
              <span className={segment.value === 0 ? 'text-text-faint' : 'text-text-muted'}>
                {segment.label}
              </span>
              <span
                className={`tabular-nums ${segment.value === 0 ? 'text-text-faint' : 'font-medium text-text'}`}
              >
                {segment.value}
              </span>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}
