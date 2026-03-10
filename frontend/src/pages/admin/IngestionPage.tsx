import { useCallback, useState } from 'react';
import { AdminPageHeader } from '@/components/admin/layout/AdminShell';
import { LiveIndicator } from '@/components/admin/layout/LiveIndicator';
import { JobDrawer } from '@/components/admin/ingestion/JobDrawer';
import { JobsTable } from '@/components/admin/ingestion/JobsTable';
import { TriggerIngestionCard } from '@/components/admin/ingestion/TriggerIngestionCard';
import { MockBadge } from '@/components/ui/MockBadge';
import { Pagination } from '@/components/ui/Pagination';
import { Panel } from '@/components/ui/Panel';
import { SearchInput } from '@/components/ui/SearchInput';
import { Select } from '@/components/ui/Select';
import { useAdminLayout } from '@/hooks/useAdminLayout';
import { usePanelData } from '@/hooks/usePanelData';
import { useQueryParamNumber, useQueryParamState } from '@/hooks/useQueryParamState';
import { adminTransport } from '@/lib/admin/transport';
import type { DocType, IngestionJob, JobStatus } from '@/lib/admin/types';

const PAGE_SIZE = 25;

export function IngestionPage() {
  const { openMobileNav } = useAdminLayout();
  const [selectedJob, setSelectedJob] = useState<IngestionJob | null>(null);
  const [retryingId, setRetryingId] = useState<string | null>(null);

  // Filters live in the URL so a filtered view is shareable and the back button
  // steps through filter states rather than leaving the page.
  const [status, setStatus] = useQueryParamState('status', 'all');
  const [docType, setDocType] = useQueryParamState('type', 'all');
  const [search, setSearch] = useQueryParamState('q', '');
  const [page, setPage] = useQueryParamNumber('page', 1);

  const offset = (page - 1) * PAGE_SIZE;
  const isFiltered = status !== 'all' || docType !== 'all' || search !== '';

  const jobs = usePanelData(
    'jobs',
    (signal) =>
      adminTransport.listIngestionJobs(
        {
          status: status as JobStatus | 'all',
          docType: docType as DocType | 'all',
          search,
          limit: PAGE_SIZE,
          offset,
        },
        signal,
      ),
    { deps: [status, docType, search, offset] },
  );

  const handleRetry = useCallback(
    async (job: IngestionJob) => {
      setRetryingId(job.id);
      const controller = new AbortController();
      try {
        await adminTransport.retryJob(job.id, controller.signal);
        jobs.refresh();
        setSelectedJob(null);
      } catch (err) {
        console.warn('retry request failed', err);
      } finally {
        setRetryingId(null);
      }
    },
    [jobs],
  );

  return (
    <>
      <AdminPageHeader
        title="Content ingestion"
        description="Trigger runs and inspect the ingest history"
        onOpenNav={openMobileNav}
        actions={<LiveIndicator />}
      />

      <div className="flex flex-col gap-4 p-4">
        <TriggerIngestionCard onTriggered={jobs.refresh} />

        <Panel
          title="Ingestion history"
          eyebrow="Ops log"
          flush
          actions={
            jobs.mocked && jobs.note ? <MockBadge reason={jobs.note} /> : undefined
          }
        >
          <div className="flex flex-wrap items-end gap-2 px-4 pb-3">
            <Select
              label="Status"
              value={status}
              onChange={setStatus}
              options={[
                { value: 'all', label: 'All statuses' },
                { value: 'queued', label: 'Queued' },
                { value: 'running', label: 'Running' },
                { value: 'done', label: 'Done' },
                { value: 'failed', label: 'Failed' },
              ]}
            />
            <Select
              label="Type"
              value={docType}
              onChange={setDocType}
              options={[
                { value: 'all', label: 'All types' },
                { value: 'case', label: 'Cases' },
                { value: 'policy', label: 'Policies' },
              ]}
            />
            <SearchInput
              value={search}
              onChange={setSearch}
              placeholder="Search by document or id…"
              className="min-w-[200px] flex-1"
            />
          </div>

          <JobsTable
            jobs={jobs}
            onSelect={setSelectedJob}
            activeJobId={selectedJob?.id ?? null}
            onRetry={handleRetry}
            retryingId={retryingId}
            emptyIsFiltered={isFiltered}
          />

          <Pagination
            total={jobs.data?.total ?? 0}
            limit={PAGE_SIZE}
            offset={offset}
            onChange={(nextOffset) => setPage(Math.floor(nextOffset / PAGE_SIZE) + 1)}
            className="border-t border-border"
          />
        </Panel>
      </div>

      <JobDrawer
        job={selectedJob}
        onClose={() => setSelectedJob(null)}
        onRetry={handleRetry}
        retrying={retryingId === selectedJob?.id}
      />
    </>
  );
}
