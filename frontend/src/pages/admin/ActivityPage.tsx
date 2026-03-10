import { Bot, Clock, SearchX } from 'lucide-react';
import { useState } from 'react';
import { AdminPageHeader } from '@/components/admin/layout/AdminShell';
import { LiveIndicator } from '@/components/admin/layout/LiveIndicator';
import { RunDrawer } from '@/components/admin/activity/RunDrawer';
import { DataTable, type Column } from '@/components/ui/DataTable';
import { EmptyState } from '@/components/ui/EmptyState';
import { MockBadge } from '@/components/ui/MockBadge';
import { Pagination } from '@/components/ui/Pagination';
import { Panel } from '@/components/ui/Panel';
import { SearchInput } from '@/components/ui/SearchInput';
import { Select } from '@/components/ui/Select';
import { StatCard } from '@/components/ui/StatCard';
import { ConfidenceChip, RunStatusPill } from '@/components/ui/StatusPill';
import { useAdminLayout } from '@/hooks/useAdminLayout';
import { useNow } from '@/hooks/useNow';
import { usePanelData } from '@/hooks/usePanelData';
import { useQueryParamNumber, useQueryParamState } from '@/hooks/useQueryParamState';
import { formatCount, formatCurrency, formatDuration, formatPercent, formatRelativeTime, truncate } from '@/lib/format';
import { AGENT_ACTION_TYPES, agentActionLabel } from '@/lib/status';
import { departmentLabel } from '@/lib/admin/mockTransport';
import { adminTransport } from '@/lib/admin/transport';
import type { AgentActionType, AgentRun, AgentRunStatus } from '@/lib/admin/types';

const PAGE_SIZE = 25;

const DATE_RANGES = [
  { value: 'all', label: 'All time', days: null },
  { value: '1', label: 'Last 24 hours', days: 1 },
  { value: '7', label: 'Last 7 days', days: 7 },
  { value: '30', label: 'Last 30 days', days: 30 },
];

export function ActivityPage() {
  const { openMobileNav } = useAdminLayout();
  const now = useNow(10_000);
  const [selectedRun, setSelectedRun] = useState<AgentRun | null>(null);

  const [status, setStatus] = useQueryParamState('status', 'all');
  const [actionType, setActionType] = useQueryParamState('action', 'all');
  const [range, setRange] = useQueryParamState('range', 'all');
  const [search, setSearch] = useQueryParamState('q', '');
  const [page, setPage] = useQueryParamNumber('page', 1);

  const offset = (page - 1) * PAGE_SIZE;
  const rangeDays = DATE_RANGES.find((entry) => entry.value === range)?.days ?? null;
  const from = rangeDays ? new Date(Date.now() - rangeDays * 86_400_000).toISOString() : undefined;
  const isFiltered = status !== 'all' || actionType !== 'all' || range !== 'all' || search !== '';

  const runs = usePanelData(
    'agent-runs',
    (signal) =>
      adminTransport.listAgentRuns(
        {
          status: status as AgentRunStatus | 'all',
          actionType: actionType as AgentActionType | 'all',
          search,
          from,
          limit: PAGE_SIZE,
          offset,
        },
        signal,
      ),
    { deps: [status, actionType, range, search, offset] },
  );

  const items = runs.data?.items ?? [];
  const noMatchRate =
    items.length === 0
      ? null
      : items.filter((run) => run.status === 'no_match').length / items.length;
  const latencies = items
    .map((run) => run.totalLatencyMs)
    .filter((value): value is number => value !== null)
    .sort((a, b) => a - b);
  const medianLatency = latencies.length ? latencies[Math.floor(latencies.length / 2)] : null;

  const columns: Column<AgentRun>[] = [
    {
      key: 'started',
      header: 'Started',
      width: 'w-[96px]',
      render: (run) => (
        <span className="font-mono text-[11.5px] text-text-faint">
          {formatRelativeTime(run.startedAt, now)}
        </span>
      ),
    },
    {
      key: 'query',
      header: 'Question',
      render: (run) => (
        <span className="block truncate" title={run.inputSummary}>
          {truncate(run.inputSummary, 90)}
        </span>
      ),
    },
    {
      key: 'department',
      header: 'Department',
      width: 'w-[172px]',
      secondary: true,
      render: (run) => (
        <span className="flex items-center gap-1.5">
          <span className="min-w-0 truncate text-text-muted">{departmentLabel(run.department)}</span>
          <ConfidenceChip value={run.confidence} />
        </span>
      ),
    },
    {
      key: 'status',
      header: 'Status',
      width: 'w-[108px]',
      render: (run) => <RunStatusPill status={run.status} />,
    },
    {
      key: 'steps',
      header: 'Steps',
      width: 'w-[64px]',
      numeric: true,
      secondary: true,
      render: (run) => <span className="text-text-muted">{run.actions.length}</span>,
    },
    {
      key: 'latency',
      header: 'Latency',
      width: 'w-[80px]',
      numeric: true,
      render: (run) => (
        <span className="text-text-muted">{formatDuration(run.totalLatencyMs)}</span>
      ),
    },
    {
      key: 'cost',
      header: 'Cost',
      width: 'w-[76px]',
      numeric: true,
      secondary: true,
      render: (run) => <span className="text-text-faint">{formatCurrency(run.costUsd)}</span>,
    },
  ];

  return (
    <>
      <AdminPageHeader
        title="Agent activity"
        description="Graph executions, routing decisions and latency"
        onOpenNav={openMobileNav}
        actions={<LiveIndicator />}
      />

      <div className="flex flex-col gap-4 p-4">
        <MockBadge
          variant="banner"
          reason="No agent exists yet. The RAG graph in lld.md §6 (analyze_query → retrieve → grade_documents → generate → check_groundedness) has not been built, so this page renders the contract it will emit rather than real runs. See backend/docs/admin-api.md."
        />

        <div className="grid grid-cols-1 gap-4 sm:grid-cols-3">
          <StatCard
            label="Runs in view"
            value={formatCount(runs.data?.total ?? 0)}
            icon={<Bot size={15} strokeWidth={1.75} />}
            status={runs.status}
            mocked
            mockReason="No agent runs are recorded yet."
          />
          <StatCard
            label="No-match rate"
            value={formatPercent(noMatchRate, 1)}
            hint="declined rather than guessed"
            // Info, not danger: a system that correctly abstains did its job,
            // and colouring it red would train operators to treat honest
            // uncertainty as breakage.
            tone="info"
            icon={<SearchX size={15} strokeWidth={1.75} />}
            status={runs.status}
            mocked
            mockReason="No agent runs are recorded yet."
          />
          <StatCard
            label="Median latency"
            value={formatDuration(medianLatency)}
            hint={`across ${latencies.length} runs on this page`}
            icon={<Clock size={15} strokeWidth={1.75} />}
            status={runs.status}
            mocked
            mockReason="No agent runs are recorded yet."
          />
        </div>

        <Panel title="Execution history" eyebrow="Runs" flush>
          <div className="flex flex-wrap items-end gap-2 px-4 pb-3">
            <Select
              label="Status"
              value={status}
              onChange={setStatus}
              options={[
                { value: 'all', label: 'All statuses' },
                { value: 'succeeded', label: 'Succeeded' },
                { value: 'no_match', label: 'No match' },
                { value: 'failed', label: 'Failed' },
                { value: 'running', label: 'Running' },
              ]}
            />
            <Select
              label="Graph node"
              value={actionType}
              onChange={setActionType}
              options={[
                { value: 'all', label: 'Any node' },
                ...AGENT_ACTION_TYPES.map((type) => ({
                  value: type,
                  label: agentActionLabel(type),
                })),
              ]}
            />
            <Select
              label="Period"
              value={range}
              onChange={setRange}
              options={DATE_RANGES.map(({ value, label }) => ({ value, label }))}
            />
            <SearchInput
              value={search}
              onChange={setSearch}
              placeholder="Search questions and answers…"
              className="min-w-[200px] flex-1"
            />
          </div>

          <DataTable
            caption="Agent graph executions, newest first"
            columns={columns}
            rows={items}
            rowKey={(run) => run.id}
            status={runs.status}
            error={runs.error}
            errorDetail={runs.errorDetail}
            failureCount={runs.failureCount}
            onRetry={runs.refresh}
            // Wrapped rather than passed directly: a state setter also accepts
            // an updater function, which makes DataTable's generic infer the
            // union instead of AgentRun.
            onRowClick={(run) => setSelectedRun(run)}
            activeRowKey={selectedRun?.id ?? null}
            skeletonRows={8}
            empty={
              <EmptyState
                icon={<Bot size={18} strokeWidth={1.5} />}
                title={isFiltered ? 'No runs match these filters' : 'No agent runs recorded'}
                description={
                  isFiltered
                    ? 'Try widening the status, node or period filter.'
                    : 'Runs will appear here once the RAG graph is built and instrumented.'
                }
              />
            }
          />

          <Pagination
            total={runs.data?.total ?? 0}
            limit={PAGE_SIZE}
            offset={offset}
            onChange={(nextOffset) => setPage(Math.floor(nextOffset / PAGE_SIZE) + 1)}
            className="border-t border-border"
          />
        </Panel>
      </div>

      <RunDrawer run={selectedRun} onClose={() => setSelectedRun(null)} />
    </>
  );
}
