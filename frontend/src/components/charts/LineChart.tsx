import { useMemo, useState } from 'react';
import { buildAreaPath, buildLinePath, linearScale, maxOf, niceMax, thinLabels } from './scale';

export interface LineSeries {
  key: string;
  label: string;
  /** Tailwind stroke utility, e.g. `stroke-accent`. Complete literal, never interpolated. */
  strokeClass: string;
  /** Tailwind fill utility for the area under the line, e.g. `fill-accent/10`. */
  areaClass?: string;
  values: number[];
}

interface LineChartProps {
  width: number;
  height: number;
  /** Pre-formatted x labels, one per point in every series. */
  labels: string[];
  series: LineSeries[];
  yFormat?(value: number): string;
  /** Pins the y-domain top. Pass 1 for rate charts so 4% does not fill the frame. */
  yMax?: number;
}

const PADDING = { top: 8, right: 8, bottom: 20, left: 36 };

/**
 * A multi-series line chart with a shared crosshair.
 *
 * Colour comes from Tailwind utility classes rather than inline values on
 * purpose. A palette switch flips a `data-palette` attribute on `<html>` with
 * no React re-render, so anything read via `getComputedStyle` would stay stale
 * until the next poll. Classes resolve through `var()` in CSS and simply follow.
 *
 * Note also that `fill="var(--accent)"` as a bare SVG presentation attribute
 * silently renders black — `var()` is only honoured in `style` or through a
 * real CSS rule, which is what these utilities are.
 */
export function LineChart({ width, height, labels, series, yFormat, yMax }: LineChartProps) {
  const [activeIndex, setActiveIndex] = useState<number | null>(null);

  const plotWidth = Math.max(1, width - PADDING.left - PADDING.right);
  const plotHeight = Math.max(1, height - PADDING.top - PADDING.bottom);

  const domainMax = yMax ?? niceMax(maxOf(series.map((entry) => entry.values)));

  const x = useMemo(
    () => linearScale([0, Math.max(1, labels.length - 1)], [PADDING.left, PADDING.left + plotWidth]),
    [labels.length, plotWidth],
  );
  const y = useMemo(
    () => linearScale([0, domainMax], [PADDING.top + plotHeight, PADDING.top]),
    [domainMax, plotHeight],
  );

  const gridValues = y.domain === undefined ? [] : [0, 0.25, 0.5, 0.75, 1].map((f) => domainMax * f);
  const visibleLabels = thinLabels(labels, Math.max(2, Math.floor(width / 64)));

  const paths = series.map((entry) => {
    const points = entry.values.map((value, index) => [x(index), y(value)] as const);
    return {
      ...entry,
      line: buildLinePath(points),
      area: entry.areaClass ? buildAreaPath(points, PADDING.top + plotHeight) : null,
      points,
    };
  });

  /** Nearest data index to a pointer x, in plot coordinates. */
  const indexAt = (offsetX: number): number => {
    const ratio = (offsetX - PADDING.left) / plotWidth;
    const index = Math.round(ratio * (labels.length - 1));
    return Math.min(labels.length - 1, Math.max(0, index));
  };

  return (
    <g>
      {/* Grid + y labels */}
      {gridValues.map((value) => (
        <g key={value}>
          <line
            x1={PADDING.left}
            x2={PADDING.left + plotWidth}
            y1={y(value)}
            y2={y(value)}
            className="stroke-border"
            strokeWidth={1}
          />
          <text
            x={PADDING.left - 6}
            y={y(value) + 3}
            textAnchor="end"
            className="fill-text-faint text-[9.5px] tabular-nums"
          >
            {yFormat ? yFormat(value) : Math.round(value)}
          </text>
        </g>
      ))}

      {/* Series */}
      {paths.map((entry) => (
        <g key={entry.key}>
          {entry.area && <path d={entry.area} className={entry.areaClass} stroke="none" />}
          <path
            d={entry.line}
            fill="none"
            strokeWidth={1.75}
            strokeLinecap="round"
            strokeLinejoin="round"
            className={entry.strokeClass}
          />
        </g>
      ))}

      {/* x labels */}
      {visibleLabels.map((label, index) =>
        label === null ? null : (
          <text
            key={index}
            x={x(index)}
            y={height - 6}
            textAnchor={index === 0 ? 'start' : index === labels.length - 1 ? 'end' : 'middle'}
            className="fill-text-faint text-[9.5px] tabular-nums"
          >
            {label}
          </text>
        ),
      )}

      {/* Crosshair */}
      {activeIndex !== null && (
        <g>
          <line
            x1={x(activeIndex)}
            x2={x(activeIndex)}
            y1={PADDING.top}
            y2={PADDING.top + plotHeight}
            className="stroke-border-strong"
            strokeWidth={1}
            strokeDasharray="3 3"
          />
          {paths.map((entry) => (
            <circle
              key={entry.key}
              cx={x(activeIndex)}
              cy={y(entry.values[activeIndex] ?? 0)}
              r={3.5}
              className={`${entry.strokeClass} fill-surface`}
              strokeWidth={2}
            />
          ))}
        </g>
      )}

      {/* One transparent hit area for the whole plot rather than per-point
          targets: at 90 points the targets would be two pixels wide and
          effectively unhittable. Keyboard users step with the arrow keys. */}
      <rect
        x={PADDING.left}
        y={PADDING.top}
        width={plotWidth}
        height={plotHeight}
        fill="transparent"
        tabIndex={0}
        role="application"
        aria-label="Chart cursor. Use the left and right arrow keys to move between points."
        onPointerMove={(event) => {
          const bounds = event.currentTarget.ownerSVGElement?.getBoundingClientRect();
          if (!bounds) return;
          setActiveIndex(indexAt(event.clientX - bounds.left));
        }}
        onPointerLeave={() => setActiveIndex(null)}
        onFocus={() => setActiveIndex(0)}
        onBlur={() => setActiveIndex(null)}
        onKeyDown={(event) => {
          if (event.key === 'ArrowRight') {
            event.preventDefault();
            setActiveIndex((current) => Math.min(labels.length - 1, (current ?? -1) + 1));
          } else if (event.key === 'ArrowLeft') {
            event.preventDefault();
            setActiveIndex((current) => Math.max(0, (current ?? 1) - 1));
          } else if (event.key === 'Home') {
            event.preventDefault();
            setActiveIndex(0);
          } else if (event.key === 'End') {
            event.preventDefault();
            setActiveIndex(labels.length - 1);
          }
        }}
      />

      {/* Announced to screen readers as the cursor moves, so the keyboard
          interaction above is not silent. */}
      {activeIndex !== null && (
        <text className="sr-only" aria-live="polite">
          {labels[activeIndex]}:{' '}
          {series.map((entry) => `${entry.label} ${entry.values[activeIndex]}`).join(', ')}
        </text>
      )}
    </g>
  );
}
