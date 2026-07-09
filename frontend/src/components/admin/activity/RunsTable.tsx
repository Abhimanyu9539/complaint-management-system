import { Bot } from 'lucide-react';
import { EmptyState } from '@/components/ui/EmptyState';
import { DataTable, type Column } from '@/components/ui/DataTable';
import { ConfidenceChip, RunStatusPill, StatusPill } from '@/components/ui/StatusPill';
import { formatDuration, formatRelativeTime, titleCase } from '@/lib/format';
import { runTriggerLabel, ticketStatusLabel, ticketStatusTone } from '@/lib/status';
import { useNow } from '@/hooks/useNow';
import type { AsyncData } from '@/hooks/useAsyncData';
import type { AgentRun, Page } from '@/lib/admin/types';

interface RunsTableProps {
  runs: AsyncData<Page<AgentRun>>;
  onSelect(run: AgentRun): void;
  activeRunId?: string | null;
  /** Shown when nothing matches — differs between "no runs at all" and "no matches". */
  emptyIsFiltered?: boolean;
}

export function RunsTable({
  runs,
  onSelect,
  activeRunId = null,
  emptyIsFiltered = false,
}: RunsTableProps) {
  const now = useNow(10_000);

  const columns: Column<AgentRun>[] = [
    {
      key: 'status',
      header: 'Status',
      width: 'w-[104px]',
      render: (run) => <RunStatusPill status={run.status} />,
    },
    {
      key: 'ticket',
      header: 'Ticket',
      render: (run) => (
        <span className="flex min-w-0 items-baseline gap-2">
          <span className="shrink-0 font-mono text-[11.5px] text-text-muted">
            {run.ticketNo !== null ? `T-${run.ticketNo}` : '—'}
          </span>
          <span className="truncate" title={run.subject ?? undefined}>
            {run.subject ?? ''}
          </span>
        </span>
      ),
    },
    {
      key: 'trigger',
      header: 'Trigger',
      width: 'w-[104px]',
      secondary: true,
      render: (run) => <span className="text-text-muted">{runTriggerLabel(run.trigger)}</span>,
    },
    {
      key: 'department',
      header: 'Department',
      width: 'w-[184px]',
      secondary: true,
      render: (run) =>
        run.department ? (
          <span className="flex min-w-0 items-center gap-2">
            <span className="truncate text-text-muted">{titleCase(run.department)}</span>
            <ConfidenceChip value={run.confidence} />
          </span>
        ) : (
          <span className="text-text-faint">—</span>
        ),
    },
    {
      key: 'outcome',
      header: 'Outcome',
      width: 'w-[128px]',
      render: (run) =>
        run.outcome ? (
          <StatusPill
            label={ticketStatusLabel(run.outcome)}
            tone={ticketStatusTone(run.outcome)}
            dot={false}
          />
        ) : (
          <span className="text-text-faint">—</span>
        ),
    },
    {
      key: 'latency',
      header: 'Latency',
      width: 'w-[80px]',
      numeric: true,
      render: (run) => <span className="text-text-muted">{formatDuration(run.latencyMs)}</span>,
    },
    {
      key: 'started',
      header: 'Started',
      width: 'w-[104px]',
      numeric: true,
      secondary: true,
      render: (run) => (
        <span className="text-text-faint">{formatRelativeTime(run.startedAt, now)}</span>
      ),
    },
  ];

  return (
    <DataTable
      caption="Ticket-graph runs, newest first"
      columns={columns}
      rows={runs.data?.items ?? []}
      rowKey={(run) => run.id}
      status={runs.status}
      error={runs.error}
      errorDetail={runs.errorDetail}
      failureCount={runs.failureCount}
      onRetry={runs.refresh}
      onRowClick={onSelect}
      activeRowKey={activeRunId}
      skeletonRows={8}
      empty={
        emptyIsFiltered ? (
          <EmptyState
            icon={<Bot size={18} strokeWidth={1.5} />}
            title="No runs match these filters"
            description="Try widening the status filter or clearing the search."
          />
        ) : (
          <EmptyState
            icon={<Bot size={18} strokeWidth={1.5} />}
            title="No agent runs yet"
            description="Each new ticket, regenerate and department answer runs the ticket graph once. Submit a ticket to record the first run."
          />
        )
      }
    />
  );
}
