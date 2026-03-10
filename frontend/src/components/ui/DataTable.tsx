import type { ReactNode } from 'react';
import type { AsyncStatus } from '@/hooks/useAsyncData';
import { AsyncBoundary } from './AsyncBoundary';
import { Skeleton } from './Skeleton';

export interface Column<T> {
  key: string;
  header: string;
  /** Right-aligns and applies tabular-nums. Use for every count, duration and percentage. */
  numeric?: boolean;
  /** A Tailwind width class. Leave exactly one column without one — it flexes. */
  width?: string;
  /** Hidden below md. Use for columns that are context rather than identity. */
  secondary?: boolean;
  render(row: T): ReactNode;
}

interface DataTableProps<T> {
  columns: Column<T>[];
  rows: T[];
  rowKey(row: T): string;
  status: AsyncStatus;
  error?: string | null;
  errorDetail?: string | null;
  failureCount?: number;
  onRetry?(): void;
  onRowClick?(row: T): void;
  /** Keeps an open drawer and the row that opened it visually paired. */
  activeRowKey?: string | null;
  empty: ReactNode;
  skeletonRows?: number;
  /** Screen-reader caption. Required — an unlabelled data table is a maze. */
  caption: string;
}

/**
 * The panel's table.
 *
 * Note the absence of a horizontal scroll wrapper. Wrapping this in
 * `overflow-x-auto` would create a second scroll container, which silently
 * breaks `sticky` on the header — the header would scroll away with the body.
 * Narrow screens drop columns via `Column.secondary` instead, which is why that
 * flag exists.
 */
export function DataTable<T>({
  columns,
  rows,
  rowKey,
  status,
  error = null,
  errorDetail,
  failureCount,
  onRetry,
  onRowClick,
  activeRowKey = null,
  empty,
  skeletonRows = 6,
  caption,
}: DataTableProps<T>) {
  const skeleton = (
    <div className="flex flex-col gap-px px-4 py-2">
      {Array.from({ length: skeletonRows }, (_, index) => (
        <div key={index} className="flex items-center gap-4 py-2.5">
          {columns.map((column) => (
            <Skeleton
              key={column.key}
              className={`h-3.5 ${column.width ?? 'flex-1'} ${column.secondary ? 'hidden md:block' : ''}`}
            />
          ))}
        </div>
      ))}
    </div>
  );

  return (
    <AsyncBoundary
      status={status}
      error={error}
      errorDetail={errorDetail}
      failureCount={failureCount}
      isEmpty={rows.length === 0}
      empty={empty}
      skeleton={skeleton}
      onRetry={onRetry}
    >
      <table className="w-full border-collapse text-left">
        <caption className="sr-only">{caption}</caption>
        <thead>
          <tr>
            {columns.map((column) => (
              <th
                key={column.key}
                scope="col"
                className={`sticky top-0 z-10 border-b border-border bg-surface px-4 py-2 text-[10px] font-semibold tracking-[0.06em] text-text-faint uppercase ${
                  column.numeric ? 'text-right' : 'text-left'
                } ${column.width ?? ''} ${column.secondary ? 'hidden md:table-cell' : ''}`}
              >
                {column.header}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {rows.map((row) => {
            const key = rowKey(row);
            const isActive = key === activeRowKey;

            return (
              <tr
                key={key}
                onClick={onRowClick ? () => onRowClick(row) : undefined}
                // A row that opens a drawer is an interactive control, so it
                // needs to be reachable and activatable from the keyboard —
                // a click-only row is invisible to anyone not using a mouse.
                tabIndex={onRowClick ? 0 : undefined}
                role={onRowClick ? 'button' : undefined}
                onKeyDown={
                  onRowClick
                    ? (event) => {
                        if (event.key === 'Enter' || event.key === ' ') {
                          event.preventDefault();
                          onRowClick(row);
                        }
                      }
                    : undefined
                }
                className={`border-b border-border/60 transition-colors last:border-b-0 ${
                  onRowClick ? 'cursor-pointer hover:bg-surface-hover' : ''
                } ${isActive ? 'bg-accent-soft' : ''}`}
              >
                {columns.map((column) => (
                  <td
                    key={column.key}
                    className={`px-4 py-2.5 align-middle text-[12.5px] text-text ${
                      column.numeric ? 'text-right tabular-nums' : 'text-left'
                    } ${column.secondary ? 'hidden md:table-cell' : ''}`}
                  >
                    {column.render(row)}
                  </td>
                ))}
              </tr>
            );
          })}
        </tbody>
      </table>
    </AsyncBoundary>
  );
}
