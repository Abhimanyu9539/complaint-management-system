import { Activity, Boxes, Clock, FileCheck, Lock } from 'lucide-react';
import { AdminPageHeader } from '@/components/admin/layout/AdminShell';
import { LiveIndicator } from '@/components/admin/layout/LiveIndicator';
import { EscalationPanel } from '@/components/admin/stats/EscalationPanel';
import { BarChart } from '@/components/charts/BarChart';
import { ChartFrame } from '@/components/charts/ChartFrame';
import { LineChart } from '@/components/charts/LineChart';
import { StackedBar } from '@/components/charts/StackedBar';
import { EmptyState } from '@/components/ui/EmptyState';
import { MockBadge } from '@/components/ui/MockBadge';
import { Panel } from '@/components/ui/Panel';
import { Select } from '@/components/ui/Select';
import { StatCard } from '@/components/ui/StatCard';
import { useAdminLayout } from '@/hooks/useAdminLayout';
import { usePanelData } from '@/hooks/usePanelData';
import { useQueryParamNumber } from '@/hooks/useQueryParamState';
import { formatCount, formatDate, formatDuration, formatPercent } from '@/lib/format';
import {
  DOC_STATUS_ORDER,
  TONE_CLASSES,
  docStatusLabel,
  docStatusTone,
  quantitySeries,
} from '@/lib/status';
import { adminTransport, useMockAdmin } from '@/lib/admin/transport';
import type { DocumentCounts } from '@/lib/admin/types';

const RANGE_OPTIONS = [
  { value: '7', label: 'Last 7 days' },
  { value: '30', label: 'Last 30 days' },
  { value: '90', label: 'Last 90 days' },
];

function toSegments(counts: DocumentCounts) {
  return DOC_STATUS_ORDER.map((status) => ({
    key: status,
    label: docStatusLabel(status),
    value: counts.byStatus[status] ?? 0,
    className: TONE_CLASSES[docStatusTone(status)].dot,
  }));
}

/**
 * The metrics page.
 *
 * Laid out as a grid of `Panel`s carrying an explicit span, so adding a future
 * metric is adding one `<Panel>` rather than reworking the layout. That is the
 * "scalable for future metrics" requirement answered structurally instead of
 * by leaving room.
 */
export function StatisticsPage() {
  const { openMobileNav } = useAdminLayout();
  const [days, setDays] = useQueryParamNumber('days', 30);

  const summary = usePanelData(
    'stats-ingestion',
    (signal) => adminTransport.getIngestionSummary(days, signal),
    { intervalFactor: 2, deps: [days] },
  );
  const overview = usePanelData('stats-overview', (signal) => adminTransport.getOverview(signal));
  const storage = usePanelData('stats-storage', (signal) => adminTransport.getStorageUsage(signal), {
    intervalFactor: 2,
  });
  const apiUsage = usePanelData(
    'stats-api',
    (signal) => adminTransport.getApiUsage(days, signal),
    { intervalFactor: 2, deps: [days] },
  );

  const perDay = summary.data?.perDay ?? [];
  const dayLabels = perDay.map((bucket) => formatDate(bucket.date));
  const documents = overview.data?.documents;

  const totalIndexed =
    (documents?.cases.byStatus.indexed ?? 0) + (documents?.policies.byStatus.indexed ?? 0);
  const jobsInRange = perDay.reduce(
    (sum, bucket) => sum + (bucket.values.done ?? 0) + (bucket.values.failed ?? 0),
    0,
  );

  return (
    <>
      <AdminPageHeader
        title="System statistics"
        description="Ingestion throughput, processing times and corpus growth"
        onOpenNav={openMobileNav}
        actions={
          <div className="flex items-center gap-2">
            <Select
              label="Period"
              hideLabel
              value={String(days)}
              onChange={(value) => setDays(Number(value))}
              options={RANGE_OPTIONS}
            />
            <LiveIndicator />
          </div>
        }
      />

      <div className="grid grid-cols-1 gap-4 p-4 lg:grid-cols-2 xl:grid-cols-3">
        {/* Summary row */}
        <div className="grid grid-cols-2 gap-4 lg:col-span-2 lg:grid-cols-4 xl:col-span-3">
          <StatCard
            label="API requests"
            value={formatCount(apiUsage.data?.totalRequests)}
            hint={`last ${days} days`}
            icon={<Activity size={15} strokeWidth={1.75} />}
            status={apiUsage.status}
            mocked={apiUsage.mocked}
            mockReason={apiUsage.note ?? undefined}
          />
          <StatCard
            label="Ingest jobs"
            value={formatCount(jobsInRange)}
            hint={`${formatPercent(summary.data?.successRate, 1)} succeeded`}
            icon={<Boxes size={15} strokeWidth={1.75} />}
            status={summary.status}
            mocked={summary.mocked}
            mockReason={summary.note ?? undefined}
          />
          <StatCard
            label="Median ingest time"
            value={formatDuration(summary.data?.durations.p50Ms)}
            hint={`p95 ${formatDuration(summary.data?.durations.p95Ms)}`}
            icon={<Clock size={15} strokeWidth={1.75} />}
            status={summary.status}
            mocked={summary.mocked}
            mockReason={summary.note ?? undefined}
          />
          <StatCard
            label="Indexed documents"
            value={formatCount(totalIndexed)}
            icon={<FileCheck size={15} strokeWidth={1.75} />}
            status={overview.status}
            mocked={overview.mocked}
            mockReason={overview.note ?? undefined}
          />
        </div>

        {/* Ingestion frequency */}
        <Panel
          title="Ingestion frequency"
          eyebrow="Throughput"
          span={2}
          actions={summary.mocked && summary.note ? <MockBadge reason={summary.note} /> : undefined}
        >
          <ChartFrame
            title="Ingestion jobs per day"
            summary={`Completed and failed ingestion jobs over the last ${days} days.`}
            height={200}
            status={summary.status}
            error={summary.error}
            isEmpty={perDay.length === 0}
            onRetry={summary.refresh}
            legend={[
              // Completed is throughput, so it follows the palette; failed is a
              // status and stays red. See the rule in lib/status.ts.
              { label: 'Completed', swatchClass: 'bg-accent' },
              { label: 'Failed', swatchClass: 'bg-danger' },
            ]}
            dataTable={{
              columns: ['Date', 'Completed', 'Failed'],
              rows: perDay.map((bucket) => [
                bucket.date,
                bucket.values.done ?? 0,
                bucket.values.failed ?? 0,
              ]),
            }}
          >
            {(width) => (
              <LineChart
                width={width}
                height={200}
                labels={dayLabels}
                series={[
                  {
                    key: 'done',
                    label: 'Completed',
                    strokeClass: 'stroke-accent',
                    areaClass: 'fill-accent/10',
                    values: perDay.map((bucket) => bucket.values.done ?? 0),
                  },
                  {
                    key: 'failed',
                    label: 'Failed',
                    strokeClass: 'stroke-danger',
                    values: perDay.map((bucket) => bucket.values.failed ?? 0),
                  },
                ]}
              />
            )}
          </ChartFrame>
        </Panel>

        {/* Processing time */}
        <Panel
          title="Processing time"
          eyebrow="Latency"
          description={
            summary.data
              ? `p50 ${formatDuration(summary.data.durations.p50Ms)} · p95 ${formatDuration(summary.data.durations.p95Ms)} · max ${formatDuration(summary.data.durations.maxMs)}`
              : undefined
          }
        >
          <ChartFrame
            title="Ingest duration percentiles"
            summary="Median, 95th percentile and maximum time to ingest one document."
            height={180}
            status={summary.status}
            error={summary.error}
            isEmpty={(summary.data?.durations.samples ?? 0) === 0}
            emptyLabel="No finished jobs in this period."
            onRetry={summary.refresh}
            dataTable={{
              columns: ['Percentile', 'Duration'],
              rows: [
                ['p50', formatDuration(summary.data?.durations.p50Ms)],
                ['p95', formatDuration(summary.data?.durations.p95Ms)],
                ['max', formatDuration(summary.data?.durations.maxMs)],
              ],
            }}
          >
            {(width) => (
              <BarChart
                width={width}
                height={180}
                labels={['p50', 'p95', 'max']}
                yFormat={(value) => formatDuration(value)}
                series={[
                  {
                    key: 'duration',
                    label: 'Duration',
                    fillClass: 'fill-accent',
                    values: [
                      summary.data?.durations.p50Ms ?? 0,
                      summary.data?.durations.p95Ms ?? 0,
                      summary.data?.durations.maxMs ?? 0,
                    ],
                  },
                ]}
              />
            )}
          </ChartFrame>
        </Panel>

        {/* Documents by status */}
        <Panel title="Documents by status" eyebrow="Corpus">
          {documents ? (
            <div className="flex flex-col gap-5">
              {(
                [
                  ['Cases', documents.cases],
                  ['Policies', documents.policies],
                ] as const
              ).map(([label, counts]) => (
                <div key={label} className="flex flex-col gap-2">
                  <span className="text-[12px] font-medium text-text">{label}</span>
                  <StackedBar segments={toSegments(counts)} />
                </div>
              ))}
            </div>
          ) : (
            <EmptyState title="No document counts yet." />
          )}
        </Panel>

        {/* Documents by department */}
        <Panel title="Cases by department" eyebrow="Distribution" span={2}>
          <ChartFrame
            title="Cases per department"
            summary="How the indexed case corpus is spread across the twelve departments."
            height={300}
            status={summary.status}
            error={summary.error}
            isEmpty={(summary.data?.byDepartment.length ?? 0) === 0}
            onRetry={summary.refresh}
            dataTable={{
              columns: ['Department', 'Cases'],
              rows: (summary.data?.byDepartment ?? []).map((entry) => [entry.label, entry.cases]),
            }}
          >
            {(width) => (
              <BarChart
                width={width}
                height={300}
                horizontal
                labels={(summary.data?.byDepartment ?? []).map((entry) => entry.label)}
                series={[
                  {
                    key: 'cases',
                    label: 'Cases',
                    fillClass: 'fill-accent',
                    values: (summary.data?.byDepartment ?? []).map((entry) => entry.cases),
                  },
                ]}
              />
            )}
          </ChartFrame>
        </Panel>

        {/* Vector store */}
        <Panel title="Vector store" eyebrow="Storage">
          {storage.data ? (
            <StackedBar
              // Point counts are volume, not status, so the segments walk a
              // single palette-following ramp. The previous `bg-info` for
              // everything after the first both froze the colour against the
              // palette and collapsed to one shade at three collections.
              segments={storage.data.collections.map((collection, index) => ({
                key: collection.name,
                label: collection.name,
                value: collection.pointCount,
                className: quantitySeries(index).dot,
              }))}
            />
          ) : (
            <EmptyState title="No collection data yet." />
          )}
        </Panel>

        {/* API usage */}
        <Panel
          title="API usage"
          eyebrow="Traffic"
          span={2}
          actions={apiUsage.note ? <MockBadge reason={apiUsage.note} /> : undefined}
        >
          <ChartFrame
            title="API requests per day"
            summary={`Requests and errors per day over the last ${days} days.`}
            height={200}
            status={apiUsage.status}
            error={apiUsage.error}
            isEmpty={(apiUsage.data?.points.length ?? 0) === 0}
            onRetry={apiUsage.refresh}
            legend={[
              { label: 'Requests', swatchClass: 'bg-accent' },
              { label: 'Errors', swatchClass: 'bg-danger' },
            ]}
            dataTable={{
              columns: ['Date', 'Requests', 'Errors'],
              rows: (apiUsage.data?.points ?? []).map((point) => [
                point.date,
                point.requests,
                point.errors,
              ]),
            }}
          >
            {(width) => (
              <LineChart
                width={width}
                height={200}
                labels={(apiUsage.data?.points ?? []).map((point) => formatDate(point.date))}
                series={[
                  {
                    key: 'requests',
                    label: 'Requests',
                    strokeClass: 'stroke-accent',
                    areaClass: 'fill-accent/10',
                    values: (apiUsage.data?.points ?? []).map((point) => point.requests),
                  },
                  {
                    key: 'errors',
                    label: 'Errors',
                    strokeClass: 'stroke-danger',
                    values: (apiUsage.data?.points ?? []).map((point) => point.errors),
                  },
                ]}
              />
            )}
          </ChartFrame>
        </Panel>

        <EscalationPanel days={days} />

        <OutcomeMetricsPanel />
      </div>
    </>
  );
}

/**
 * What is left of cms.md §4.4 once escalation rate is real.
 *
 * That section names four north-star metrics. Escalation rate now has a writer
 * — the ticket queue — and lives in `EscalationPanel` above, computed from
 * `tickets.resolution_path`. The other three still have no writer: nothing
 * generates a draft, so nothing accepts or edits one, and no request is priced.
 *
 * They stay blank rather than simulated for the same reason as before. A
 * plausible draft-acceptance trend would demo well and mislead the one person
 * this page is built for, and the conditional that prevents it costs one branch.
 */
function OutcomeMetricsPanel() {
  return (
    <Panel title="Remaining outcome metrics" eyebrow="Blocked" span={3}>
      <EmptyState
        icon={<Lock size={18} strokeWidth={1.5} />}
        title="Draft acceptance, time-to-response and cost per ticket"
        description={
          useMockAdmin ? (
            <>
              These three need the drafting pipeline. The <code>drafts</code> and{' '}
              <code>draft_feedback</code> tables exist but nothing writes to them yet — no draft is
              generated, so none is accepted or edited (cms.md §6). Escalation rate, the fourth
              metric from §4.4, is live above.
            </>
          ) : (
            <>
              No data yet — <code>drafts</code> and <code>draft_feedback</code> are empty, and
              nothing prices a request. These land with the drafting pipeline; escalation rate, the
              fourth §4.4 metric, is live above.
            </>
          )
        }
      />
    </Panel>
  );
}
