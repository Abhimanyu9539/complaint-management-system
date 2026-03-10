import type { ReactNode } from 'react';
import { useElementWidth } from '@/hooks/useElementWidth';
import type { AsyncStatus } from '@/hooks/useAsyncData';
import { EmptyState } from '@/components/ui/EmptyState';
import { ErrorState } from '@/components/ui/ErrorState';
import { Skeleton } from '@/components/ui/Skeleton';

export interface ChartLegendEntry {
  label: string;
  /** A Tailwind background utility for the swatch. Complete literal. */
  swatchClass: string;
}

/** Fixed, uneven heights so the loading state reads as a chart, not a table. */
const SKELETON_BAR_HEIGHTS = [
  'h-1/3',
  'h-2/3',
  'h-1/2',
  'h-4/5',
  'h-2/5',
  'h-3/5',
  'h-full',
  'h-1/2',
  'h-3/4',
  'h-2/5',
];

interface ChartFrameProps {
  /** Accessible name of the chart. */
  title: string;
  /**
   * One sentence of plain language describing what the chart shows. Required:
   * a chart with no textual summary is invisible to anyone using a screen
   * reader, and colour alone never carries the finding.
   */
  summary: string;
  height: number;
  status: AsyncStatus;
  error?: string | null;
  isEmpty: boolean;
  emptyLabel?: string;
  onRetry?(): void;
  legend?: ChartLegendEntry[];
  /**
   * A screen-reader-only table mirroring the plotted data. Required, so a chart
   * is never the only representation of its own numbers.
   */
  dataTable: { columns: string[]; rows: (string | number)[][] };
  /** Called only once the container has been measured — never at width 0. */
  children(width: number): ReactNode;
}

/**
 * The shell every measured chart draws inside.
 *
 * Owns measurement, the load/empty/error states, the legend and the accessible
 * fallback table, so the individual chart components are only geometry.
 */
export function ChartFrame({
  title,
  summary,
  height,
  status,
  error,
  isEmpty,
  emptyLabel = 'Nothing to chart yet.',
  onRetry,
  legend,
  dataTable,
  children,
}: ChartFrameProps) {
  const [containerRef, width] = useElementWidth();

  return (
    <div className="flex min-w-0 flex-col gap-3">
      {legend && legend.length > 0 && status !== 'loading' && !isEmpty && (
        <ul className="flex flex-wrap items-center gap-x-3 gap-y-1">
          {legend.map((entry) => (
            <li key={entry.label} className="flex items-center gap-1.5 text-[11px] text-text-muted">
              <span aria-hidden="true" className={`h-2 w-2 rounded-full ${entry.swatchClass}`} />
              {entry.label}
            </li>
          ))}
        </ul>
      )}

      <div ref={containerRef} className="min-w-0" style={{ minHeight: height }}>
        {status === 'loading' ? (
          <div className="flex w-full items-end gap-1.5" style={{ height }}>
            {/* Bar-shaped skeleton rather than one block: it sets the right
                expectation for what is about to appear in the same space. */}
            {SKELETON_BAR_HEIGHTS.map((barHeight, index) => (
              <Skeleton key={index} className={`flex-1 ${barHeight}`} />
            ))}
          </div>
        ) : status === 'error' && isEmpty ? (
          <ErrorState message={error ?? 'Could not load this chart.'} onRetry={onRetry} />
        ) : isEmpty ? (
          <EmptyState title={emptyLabel} />
        ) : (
          // Gated on a real measurement: drawing at width 0 puts every point at
          // the same coordinate for one frame, which flashes as a collapsed
          // chart before the first ResizeObserver callback lands.
          width > 0 && (
            <svg
              width={width}
              height={height}
              role="img"
              aria-label={`${title}. ${summary}`}
              className="block overflow-visible"
            >
              {children(width)}
            </svg>
          )
        )}
      </div>

      {!isEmpty && status !== 'loading' && (
        <table className="sr-only">
          <caption>{`${title}. ${summary}`}</caption>
          <thead>
            <tr>
              {dataTable.columns.map((column) => (
                <th key={column} scope="col">
                  {column}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {dataTable.rows.map((row, index) => (
              <tr key={index}>
                {row.map((cell, cellIndex) => (
                  <td key={cellIndex}>{cell}</td>
                ))}
              </tr>
            ))}
          </tbody>
        </table>
      )}
    </div>
  );
}
