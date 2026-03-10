import { CircleAlert, FileCheck, Loader, TrendingUp } from 'lucide-react';
import { useCallback, useState } from 'react';
import { Link } from 'react-router';
import { AdminPageHeader } from '@/components/admin/layout/AdminShell';
import { LiveIndicator } from '@/components/admin/layout/LiveIndicator';
import { DocumentCountsPanel } from '@/components/admin/dashboard/DocumentCountsPanel';
import { HealthPanel } from '@/components/admin/dashboard/HealthPanel';
import { QueuePanel } from '@/components/admin/dashboard/QueuePanel';
import { StoragePanel } from '@/components/admin/dashboard/StoragePanel';
import { JobDrawer } from '@/components/admin/ingestion/JobDrawer';
import { JobsTable } from '@/components/admin/ingestion/JobsTable';
import { Panel } from '@/components/ui/Panel';
import { StatCard } from '@/components/ui/StatCard';
import { useAdminLayout } from '@/hooks/useAdminLayout';
import { usePanelData } from '@/hooks/usePanelData';
import { formatCount, formatPercent } from '@/lib/format';
import { adminTransport } from '@/lib/admin/transport';
import type { IngestionJob } from '@/lib/admin/types';

const RECENT_JOBS_LIMIT = 5;
const TREND_DAYS = 14;

export function DashboardPage() {
  const { openMobileNav } = useAdminLayout();
  const [selectedJob, setSelectedJob] = useState<IngestionJob | null>(null);
  const [rerunningId, setRerunningId] = useState<string | null>(null);

  const overview = usePanelData('overview', (signal) => adminTransport.getOverview(signal));

  const summary = usePanelData(
    'ingestion-summary',
    (signal) => adminTransport.getIngestionSummary(TREND_DAYS, signal),
    { intervalFactor: 2 },
  );

  const recentJobs = usePanelData('recent-jobs', (signal) =>
    adminTransport.listIngestionJobs({ limit: RECENT_JOBS_LIMIT, offset: 0 }, signal),
  );

  /**
   * Re-runs a stuck document. Contract-only today, so the transport returns a
   * simulated job — but the optimistic refresh below is real, and will keep
   * working unchanged once a POST route exists.
   */
  const handleRerun = useCallback(
    async (_docType: 'case' | 'policy', documentId: string) => {
      setRerunningId(documentId);
      const controller = new AbortController();
      try {
        await adminTransport.retryJob(documentId, controller.signal);
        overview.refresh();
        recentJobs.refresh();
      } catch (err) {
        console.warn('re-run request failed', err);
      } finally {
        setRerunningId(null);
      }
    },
    [overview, recentJobs],
  );

  const documents = overview.data?.documents;
  const indexed =
    (documents?.cases.byStatus.indexed ?? 0) + (documents?.policies.byStatus.indexed ?? 0);
  const totalDocuments = (documents?.cases.total ?? 0) + (documents?.policies.total ?? 0);
  const activeJobs = (overview.data?.jobs.queued ?? 0) + (overview.data?.jobs.running ?? 0);

  // Failures in the last 24h, derived from the per-day buckets rather than
  // fetched separately — one fewer round trip for a number nobody drills into.
  const recentFailures =
    summary.data?.perDay.slice(-1).reduce((sum, bucket) => sum + (bucket.values.failed ?? 0), 0) ??
    0;

  const jobTrend = summary.data?.perDay.map(
    (bucket) => (bucket.values.done ?? 0) + (bucket.values.failed ?? 0),
  );

  return (
    <>
      <AdminPageHeader
        title="Dashboard"
        description="Ingestion health, corpus state and storage at a glance"
        onOpenNav={openMobileNav}
        actions={<LiveIndicator />}
      />

      <div className="flex flex-col gap-4 p-4">
        <HealthPanel />

        <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 xl:grid-cols-4">
          <StatCard
            label="Indexed documents"
            value={formatCount(indexed)}
            hint={`of ${formatCount(totalDocuments)} total`}
            icon={<FileCheck size={15} strokeWidth={1.75} />}
            status={overview.status}
            mocked={overview.mocked}
            mockReason={overview.note ?? undefined}
          />
          <StatCard
            label="Active jobs"
            value={formatCount(activeJobs)}
            hint={activeJobs > 0 ? 'ingestion in progress' : 'queue is clear'}
            tone={activeJobs > 0 ? 'accent' : 'neutral'}
            icon={<Loader size={15} strokeWidth={1.75} />}
            status={overview.status}
            mocked={overview.mocked}
            mockReason={overview.note ?? undefined}
          />
          <StatCard
            label="Failed today"
            value={formatCount(recentFailures)}
            hint={recentFailures > 0 ? 'needs attention' : 'no failures'}
            tone={recentFailures > 0 ? 'danger' : 'ok'}
            icon={<CircleAlert size={15} strokeWidth={1.75} />}
            status={summary.status}
            mocked={summary.mocked}
            mockReason={summary.note ?? undefined}
          />
          <StatCard
            label={`Success rate (${TREND_DAYS}d)`}
            value={formatPercent(summary.data?.successRate, 1)}
            hint={`${formatCount(summary.data?.durations.samples ?? 0)} finished jobs`}
            tone={
              summary.data?.successRate === null || summary.data?.successRate === undefined
                ? 'neutral'
                : summary.data.successRate >= 0.95
                  ? 'ok'
                  : summary.data.successRate >= 0.8
                    ? 'warn'
                    : 'danger'
            }
            trend={jobTrend}
            icon={<TrendingUp size={15} strokeWidth={1.75} />}
            status={summary.status}
            mocked={summary.mocked}
            mockReason={summary.note ?? undefined}
          />
        </div>

        <QueuePanel overview={overview} onRerun={handleRerun} rerunningId={rerunningId} />

        <div className="grid grid-cols-1 gap-4 lg:grid-cols-2">
          <DocumentCountsPanel overview={overview} />
          <StoragePanel />
        </div>

        <Panel
          title="Recent ingestion jobs"
          eyebrow="Activity"
          flush
          actions={
            <Link
              to="/admin/ingestion"
              className="text-[11px] font-medium text-accent hover:underline"
            >
              View all
            </Link>
          }
        >
          <JobsTable jobs={recentJobs} onSelect={setSelectedJob} compact />
        </Panel>
      </div>

      <JobDrawer job={selectedJob} onClose={() => setSelectedJob(null)} />
    </>
  );
}
