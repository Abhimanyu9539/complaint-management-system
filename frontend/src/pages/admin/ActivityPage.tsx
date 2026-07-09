import { Activity, ClipboardCheck, Gauge, Timer } from 'lucide-react';
import { useState } from 'react';
import { AdminPageHeader } from '@/components/admin/layout/AdminShell';
import { LiveIndicator } from '@/components/admin/layout/LiveIndicator';
import { NodeLatencyPanel } from '@/components/admin/activity/NodeLatencyPanel';
import { RunDrawer } from '@/components/admin/activity/RunDrawer';
import { RunsTable } from '@/components/admin/activity/RunsTable';
import { Pagination } from '@/components/ui/Pagination';
import { Panel } from '@/components/ui/Panel';
import { SearchInput } from '@/components/ui/SearchInput';
import { Select } from '@/components/ui/Select';
import { StatCard } from '@/components/ui/StatCard';
import { useAdminLayout } from '@/hooks/useAdminLayout';
import { usePanelData } from '@/hooks/usePanelData';
import { useQueryParamNumber, useQueryParamState } from '@/hooks/useQueryParamState';
import { adminTransport } from '@/lib/admin/transport';
import { formatCount, formatDuration, formatPercent } from '@/lib/format';
import { RUN_STATUS_ORDER, agentNodeLabel, runStatusLabel } from '@/lib/status';
import type { AgentRun, AgentRunStatus } from '@/lib/admin/types';

const PAGE_SIZE = 25;
const SUMMARY_DAYS = 7;

/** Ticket-graph runs: one row per run, with its path, routing decisions and node timings. */
export function ActivityPage() {
  const { openMobileNav } = useAdminLayout();
  const [selectedRun, setSelectedRun] = useState<AgentRun | null>(null);

  // Filters live in the URL, like the ingestion log.
  const [status, setStatus] = useQueryParamState('status', 'all');
  const [search, setSearch] = useQueryParamState('q', '');
  const [page, setPage] = useQueryParamNumber('page', 1);

  const offset = (page - 1) * PAGE_SIZE;
  const isFiltered = status !== 'all' || search !== '';

  const summary = usePanelData('agent-summary', (signal) =>
    adminTransport.getAgentSummary(SUMMARY_DAYS, signal),
  );
  const runs = usePanelData(
    'agent-runs',
    (signal) =>
      adminTransport.listAgentRuns(
        { status: status as AgentRunStatus | 'all', search, limit: PAGE_SIZE, offset },
        signal,
      ),
    { deps: [status, search, offset] },
  );

  const data = summary.data;
  const slowest = data?.nodeLatency[0];
  const failed = data?.byStatus.failed ?? 0;

  return (
    <>
      <AdminPageHeader
        title="Agent activity"
        description="Graph executions, routing decisions and latency"
        onOpenNav={openMobileNav}
        actions={<LiveIndicator />}
      />

      <div className="flex flex-col gap-4 p-4">
        <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 xl:grid-cols-4">
          <StatCard
            label={`Runs (${SUMMARY_DAYS}d)`}
            value={formatCount(data?.total)}
            hint={failed > 0 ? `${formatCount(failed)} failed` : 'no failures'}
            tone={failed > 0 ? 'danger' : 'neutral'}
            icon={<Activity size={15} strokeWidth={1.75} />}
            status={summary.status}
          />
          <StatCard
            label="Needs review"
            value={formatPercent(data?.needsReviewRate)}
            hint="of runs gated to a person"
            icon={<ClipboardCheck size={15} strokeWidth={1.75} />}
            status={summary.status}
          />
          <StatCard
            label="Graph latency p50"
            value={formatDuration(data?.latency.p50Ms)}
            hint={`p95 ${formatDuration(data?.latency.p95Ms)}`}
            icon={<Gauge size={15} strokeWidth={1.75} />}
            status={summary.status}
          />
          <StatCard
            label="Slowest node"
            value={slowest ? formatDuration(slowest.p50Ms) : '—'}
            hint={slowest ? `${agentNodeLabel(slowest.node)} (median)` : 'no runs yet'}
            icon={<Timer size={15} strokeWidth={1.75} />}
            status={summary.status}
          />
        </div>

        <NodeLatencyPanel summary={summary} />

        <Panel title="Execution history" eyebrow="Runs" flush>
          <div className="flex flex-wrap items-end gap-2 px-4 pb-3">
            <Select
              label="Status"
              value={status}
              onChange={setStatus}
              options={[
                { value: 'all', label: 'All statuses' },
                ...RUN_STATUS_ORDER.map((value) => ({ value, label: runStatusLabel(value) })),
              ]}
            />
            <SearchInput
              value={search}
              onChange={setSearch}
              placeholder="Search by ticket number or subject…"
              className="min-w-[200px] flex-1"
            />
          </div>

          <RunsTable
            runs={runs}
            onSelect={setSelectedRun}
            activeRunId={selectedRun?.id ?? null}
            emptyIsFiltered={isFiltered}
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
