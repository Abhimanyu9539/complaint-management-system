import { useState } from 'react';
import { bandScale, linearScale, niceMax, thinLabels } from './scale';

export interface BarSeries {
  key: string;
  label: string;
  /** Tailwind fill utility, e.g. `fill-accent`. Complete literal, never interpolated. */
  fillClass: string;
  values: number[];
}

interface BarChartProps {
  width: number;
  height: number;
  labels: string[];
  /** One series, or several to stack. Stack order is array order, bottom-up. */
  series: BarSeries[];
  yFormat?(value: number): string;
  /** Lays the bars horizontally — better when the category labels are words. */
  horizontal?: boolean;
}

const PADDING = { top: 8, right: 8, bottom: 20, left: 36 };
const HORIZONTAL_PADDING = { top: 4, right: 32, bottom: 4, left: 116 };

/**
 * A stacked bar chart, vertical by default.
 *
 * `horizontal` exists for the department breakdown: twelve department names
 * cannot be read on a vertical axis without rotating them 45°, and rotated
 * labels are slower to read than a horizontal layout that simply fits them.
 */
export function BarChart({
  width,
  height,
  labels,
  series,
  yFormat,
  horizontal = false,
}: BarChartProps) {
  const [activeIndex, setActiveIndex] = useState<number | null>(null);

  // Stacked totals, not per-series maxima — a domain sized to one series would
  // let the stack overflow the plot.
  const totals = labels.map((_, index) =>
    series.reduce((sum, entry) => sum + (entry.values[index] ?? 0), 0),
  );
  const domainMax = niceMax(Math.max(...totals, 0));

  if (horizontal) {
    const plotWidth = Math.max(1, width - HORIZONTAL_PADDING.left - HORIZONTAL_PADDING.right);
    const plotHeight = Math.max(1, height - HORIZONTAL_PADDING.top - HORIZONTAL_PADDING.bottom);
    const band = bandScale(labels.length, [HORIZONTAL_PADDING.top, HORIZONTAL_PADDING.top + plotHeight], 0.3);
    const x = linearScale([0, domainMax], [0, plotWidth]);

    return (
      <g>
        {labels.map((label, index) => {
          let offset = HORIZONTAL_PADDING.left;
          return (
            <g
              key={label}
              onPointerEnter={() => setActiveIndex(index)}
              onPointerLeave={() => setActiveIndex(null)}
              className={activeIndex !== null && activeIndex !== index ? 'opacity-50' : undefined}
            >
              <text
                x={HORIZONTAL_PADDING.left - 8}
                y={band.at(index) + band.bandwidth / 2 + 3}
                textAnchor="end"
                className="fill-text-muted text-[10px]"
              >
                {label}
              </text>
              {series.map((entry) => {
                const value = entry.values[index] ?? 0;
                const barWidth = x(value);
                const rect = (
                  <rect
                    key={entry.key}
                    x={offset}
                    y={band.at(index)}
                    width={Math.max(0, barWidth)}
                    height={band.bandwidth}
                    rx={2}
                    className={entry.fillClass}
                  />
                );
                offset += barWidth;
                return rect;
              })}
              <text
                x={offset + 6}
                y={band.at(index) + band.bandwidth / 2 + 3}
                className="fill-text-faint text-[10px] tabular-nums"
              >
                {totals[index]}
              </text>
            </g>
          );
        })}
      </g>
    );
  }

  const plotWidth = Math.max(1, width - PADDING.left - PADDING.right);
  const plotHeight = Math.max(1, height - PADDING.top - PADDING.bottom);
  const band = bandScale(labels.length, [PADDING.left, PADDING.left + plotWidth], 0.28);
  const y = linearScale([0, domainMax], [PADDING.top + plotHeight, PADDING.top]);
  const visibleLabels = thinLabels(labels, Math.max(2, Math.floor(width / 52)));

  return (
    <g>
      {[0, 0.25, 0.5, 0.75, 1].map((fraction) => {
        const value = domainMax * fraction;
        return (
          <g key={fraction}>
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
        );
      })}

      {labels.map((label, index) => {
        let stackTop = PADDING.top + plotHeight;
        return (
          <g
            key={label}
            onPointerEnter={() => setActiveIndex(index)}
            onPointerLeave={() => setActiveIndex(null)}
            className={activeIndex !== null && activeIndex !== index ? 'opacity-50' : undefined}
          >
            <title>{`${label}: ${totals[index]}`}</title>
            {series.map((entry) => {
              const value = entry.values[index] ?? 0;
              const barHeight = (PADDING.top + plotHeight) - y(value);
              stackTop -= barHeight;
              return (
                <rect
                  key={entry.key}
                  x={band.at(index)}
                  y={stackTop}
                  width={band.bandwidth}
                  height={Math.max(0, barHeight)}
                  rx={2}
                  className={entry.fillClass}
                />
              );
            })}
          </g>
        );
      })}

      {visibleLabels.map((label, index) =>
        label === null ? null : (
          <text
            key={index}
            x={band.at(index) + band.bandwidth / 2}
            y={height - 6}
            textAnchor="middle"
            className="fill-text-faint text-[9.5px] tabular-nums"
          >
            {label}
          </text>
        ),
      )}
    </g>
  );
}
