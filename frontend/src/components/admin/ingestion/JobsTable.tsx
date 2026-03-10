import { Inbox, RotateCw } from 'lucide-react';
import { CommandHint, EmptyState } from '@/components/ui/EmptyState';
import { DataTable, type Column } from '@/components/ui/DataTable';
import { IconButton } from '@/components/ui/IconButton';
import { JobStatusPill } from '@/components/ui/StatusPill';
import { formatCount, formatDuration, formatRelativeTime, titleCase } from '@/lib/format';
import { useNow } from '@/hooks/useNow';
import type { AsyncData } from '@/hooks/useAsyncData';
import type { IngestionJob, Page } from '@/lib/admin/types';

interface JobsTableProps {
  jobs: AsyncData<Page<IngestionJob>>;
  onSelect(job: IngestionJob): void;
  activeJobId?: string | null;
  onRetry?(job: IngestionJob): void;
  retryingId?: string | null;
  /** Trims the table to the columns that fit a narrow dashboard card. */
  compact?: boolean;
  /** Shown when nothing matches — differs between "no jobs at all" and "no matches". */
  emptyIsFiltered?: boolean;
}

export function JobsTable({
  jobs,
  onSelect,
  activeJobId = null,
  onRetry,
  retryingId = null,
  compact = false,
  emptyIsFiltered = false,
}: JobsTableProps) {
  const now = useNow(10_000);

  const columns: Column<IngestionJob>[] = [
    {
      key: 'status',
      header: 'Status',
      width: 'w-[104px]',
      render: (job) => <JobStatusPill status={job.status} />,
    },
    {
      key: 'document',
      header: 'Document',
      render: (job) =>
        job.documentTitle ? (
          <span className="block truncate" title={job.documentTitle}>
            {job.documentTitle}
          </span>
        ) : (
          // The ops log has no FK on document_id by design, so a job can outlive
          // its document. Rendering the bare id plus "deleted" makes that
          // visible; a blank cell would read as missing data.
          <span className="flex min-w-0 items-center gap-1.5">
            <span className="truncate font-mono text-[11.5px] text-text-faint">
              {job.documentId}
            </span>
            <span className="shrink-0 text-[11px] text-text-faint italic">deleted</span>
          </span>
        ),
    },
    {
      key: 'type',
      header: 'Type',
      width: 'w-[80px]',
      secondary: compact,
      render: (job) => <span className="text-text-muted">{titleCase(job.docType)}</span>,
    },
    {
      key: 'chunks',
      header: 'Chunks',
      width: 'w-[72px]',
      numeric: true,
      secondary: true,
      render: (job) => <span className="text-text-muted">{formatCount(job.chunkCount)}</span>,
    },
    {
      key: 'points',
      header: 'Points',
      width: 'w-[72px]',
      numeric: true,
      secondary: true,
      render: (job) => <span className="text-text-muted">{formatCount(job.pointCount)}</span>,
    },
    {
      key: 'duration',
      header: 'Duration',
      width: 'w-[88px]',
      numeric: true,
      secondary: true,
      render: (job) => <span className="text-text-muted">{formatDuration(job.durationMs)}</span>,
    },
    {
      key: 'started',
      header: 'Started',
      width: 'w-[104px]',
      numeric: true,
      render: (job) => (
        <span className="text-text-faint">
          {formatRelativeTime(job.startedAt ?? job.createdAt, now)}
        </span>
      ),
    },
  ];

  if (onRetry) {
    columns.push({
      key: 'actions',
      header: '',
      width: 'w-[44px]',
      numeric: true,
      render: (job) =>
        job.status === 'failed' ? (
          <IconButton
            onClick={(event) => {
              // The row itself opens the drawer; without this the retry click
              // would also open it, burying the confirmation behind a panel.
              event.stopPropagation();
              onRetry(job);
            }}
            disabled={retryingId === job.id}
            aria-label={`Retry ingest of ${job.documentTitle ?? job.documentId}`}
            title="Retry this ingest"
            className="h-7 w-7"
          >
            <RotateCw
              size={13}
              strokeWidth={2}
              className={retryingId === job.id ? 'animate-spin' : undefined}
            />
          </IconButton>
        ) : null,
    });
  }

  const visibleColumns = compact
    ? columns.filter((column) => ['status', 'document', 'started'].includes(column.key))
    : columns;

  return (
    <DataTable
      caption="Ingestion jobs, newest first"
      columns={visibleColumns}
      rows={jobs.data?.items ?? []}
      rowKey={(job) => job.id}
      status={jobs.status}
      error={jobs.error}
      errorDetail={jobs.errorDetail}
      failureCount={jobs.failureCount}
      onRetry={jobs.refresh}
      onRowClick={onSelect}
      activeRowKey={activeJobId}
      skeletonRows={compact ? 4 : 8}
      empty={
        emptyIsFiltered ? (
          <EmptyState
            icon={<Inbox size={18} strokeWidth={1.5} />}
            title="No jobs match these filters"
            description="Try widening the status or type filter."
          />
        ) : (
          <EmptyState
            icon={<Inbox size={18} strokeWidth={1.5} />}
            title="No ingestion jobs yet"
            description={
              <>
                Index the seed corpus with <CommandHint>uv run cms-seed</CommandHint>, or trigger a
                run from the form above.
              </>
            }
          />
        )
      }
    />
  );
}
