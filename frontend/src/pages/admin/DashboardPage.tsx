import { Boxes, CircleAlert, FileCheck, Loader, TrendingUp } from 'lucide-react';
import { useCallback, useState } from 'react';
import { Link } from 'react-router';
import { AdminPageHeader } from '@/components/admin/layout/AdminShell';
import { LiveIndicator } from '@/components/admin/layout/LiveIndicator';
import { DocumentCountsPanel } from '@/components/admin/dashboard/DocumentCountsPanel';
import { HealthPanel } from '@/components/admin/dashboard/HealthPanel';
import { QueuePanel } from '@/components/admin/dashboard/QueuePanel';
import { collectionTone, StoragePanel } from '@/components/admin/dashboard/StoragePanel';
import { JobDrawer } from '@/components/admin/ingestion/JobDrawer';
import { JobsTable } from '@/components/admin/ingestion/JobsTable';
import { Panel } from '@/components/ui/Panel';
import { StatCard } from '@/components/ui/StatCard';
import { useAdminLayout } from '@/hooks/useAdminLayout';
import { usePanelData } from '@/hooks/usePanelData';
import { formatCount, formatPercent } from '@/lib/format';
import type { Tone } from '@/lib/status';
import { adminTransport } from '@/lib/admin/transport';
import type { IngestionJob } from '@/lib/admin/types';

const RECENT_JOBS_LIMIT = 5;
const TREND_DAYS = 14;

// Worst-of ordering for combining several collections' individual tones into
// one card. `ok`/`neutral`/`accent`/`info` never appear from `collectionTone`,
// so they are equally "nothing to report" here.
const TONE_SEVERITY: Record<Tone, number> = { neutral: 0, accent: 0, ok: 0, info: 0, warn: 1, danger: 2 };

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

  // 2× the base cadence — this is the only poll on this page that talks to
  // Qdrant. Owned here rather than inside `StoragePanel` so the "Vector
  // points" stat card reads the same fetch instead of doubling Qdrant traffic.
  const storage = usePanelData('storage', (signal) => adminTransport.getStorageUsage(signal), {
    intervalFactor: 2,
  });

  /**
   * Re-runs a stuck document. This is a fresh trigger, not a job retry: a
   * document stuck in `processing` has no finished/failed job row to retry —
   * the crash that stranded it may have happened before one was ever written.
   */
  const handleRerun = useCallback(
    async (docType: 'case' | 'policy', documentId: string) => {
      setRerunningId(documentId);
      const controller = new AbortController();
      try {
        await adminTransport.rerunStuckDocument(docType, documentId, controller.signal);
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
  const policiesIndexed = documents?.policies.byStatus.indexed ?? 0;
  const activeJobs = (overview.data?.jobs.queued ?? 0) + (overview.data?.jobs.running ?? 0);

  const casesIndexed = documents?.cases.byStatus.indexed ?? 0;

  const collections = storage.data?.collections ?? [];
  const vectorPoints = collections.reduce((sum, collection) => sum + collection.pointCount, 0);
  const vectorPointsTone = collections.reduce<Tone>(
    (worst, collection) =>
      TONE_SEVERITY[collectionTone(collection.status)] > TONE_SEVERITY[worst]
        ? collectionTone(collection.status)
        : worst,
    'neutral',
  );

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

        <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 xl:grid-cols-3">
          <StatCard
            label="Indexed policies"
            value={formatCount(policiesIndexed)}
            icon={<FileCheck size={15} strokeWidth={1.75} />}
            status={overview.status}
          />
          <StatCard
            label="Cases indexed"
            value={formatCount(casesIndexed)}
            icon={<FileCheck size={15} strokeWidth={1.75} />}
            status={overview.status}
          />
          <StatCard
            label="Vector points"
            value={formatCount(vectorPoints)}
            hint={
              collections.length > 0
                ? collections.map((collection) => collection.name).join(' + ')
                : 'no collections'
            }
            tone={vectorPointsTone}
            icon={<Boxes size={15} strokeWidth={1.75} />}
            status={storage.status}
          />
          <StatCard
            label="Active jobs"
            value={formatCount(activeJobs)}
            hint={activeJobs > 0 ? 'ingestion in progress' : 'queue is clear'}
            tone={activeJobs > 0 ? 'accent' : 'neutral'}
            icon={<Loader size={15} strokeWidth={1.75} />}
            status={overview.status}
          />
          <StatCard
            label="Failed today"
            value={formatCount(recentFailures)}
            hint={recentFailures > 0 ? 'needs attention' : 'no failures'}
            tone={recentFailures > 0 ? 'danger' : 'ok'}
            icon={<CircleAlert size={15} strokeWidth={1.75} />}
            status={summary.status}
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
          />
        </div>

        <QueuePanel overview={overview} onRerun={handleRerun} rerunningId={rerunningId} />

        <div className="grid grid-cols-1 gap-4 lg:grid-cols-2">
          <DocumentCountsPanel overview={overview} />
          <StoragePanel storage={storage} />
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
