import { CircleCheck, TriangleAlert } from 'lucide-react';
import { AsyncBoundary } from '@/components/ui/AsyncBoundary';
import { Button } from '@/components/ui/Button';
import { EmptyState } from '@/components/ui/EmptyState';
import { JobStatusPill } from '@/components/ui/StatusPill';
import { Panel } from '@/components/ui/Panel';
import { Skeleton } from '@/components/ui/Skeleton';
import { useNow } from '@/hooks/useNow';
import { formatRelativeTime, titleCase } from '@/lib/format';
import type { AsyncData } from '@/hooks/useAsyncData';
import type { AdminOverview } from '@/lib/admin/types';

interface QueuePanelProps {
  overview: AsyncData<AdminOverview>;
  onRerun(docType: 'case' | 'policy', documentId: string): void;
  rerunningId: string | null;
}

/**
 * What the ingestion pipeline is doing right now, and what it left behind.
 *
 * Two distinct things share this panel because an operator asks one question:
 * "is anything wrong with ingestion?" Splitting live jobs from stuck documents
 * into separate cards would make the second one easy to miss, and the second is
 * the one that needs a human.
 */
export function QueuePanel({ overview, onRerun, rerunningId }: QueuePanelProps) {
  const now = useNow(5000);
  const queue = overview.data?.queue;
  const isEmpty = !queue || (queue.active.length === 0 && queue.stuck.length === 0);

  return (
    <Panel
      title="Processing queue"
      eyebrow="Ingestion"
      actions={
        queue &&
        queue.active.length > 0 && (
          <span className="text-[11px] text-text-muted tabular-nums">
            {queue.runningCount} running · {queue.queuedCount} queued
          </span>
        )
      }
    >
      <AsyncBoundary
        status={overview.status}
        error={overview.error}
        errorDetail={overview.errorDetail}
        failureCount={overview.failureCount}
        isEmpty={isEmpty}
        onRetry={overview.refresh}
        empty={
          <EmptyState
            icon={<CircleCheck size={18} strokeWidth={1.5} className="text-ok" />}
            title="Queue is clear"
            description="No jobs in flight and nothing left in a partial state."
          />
        }
        skeleton={
          <div className="flex flex-col gap-2">
            <Skeleton className="h-11" />
            <Skeleton className="h-11" />
          </div>
        }
      >
        <div className="flex flex-col gap-4">
          {queue && queue.active.length > 0 && (
            <ul className="flex flex-col gap-1.5">
              {queue.active.map((job) => (
                <li
                  key={job.id}
                  className="flex items-center gap-3 rounded-lg border border-border bg-bg-elevated px-3 py-2"
                >
                  <JobStatusPill status={job.status} />
                  <span className="min-w-0 flex-1 truncate text-[12.5px] text-text">
                    {job.documentTitle ?? job.documentId}
                  </span>
                  <span className="shrink-0 text-[11px] text-text-faint">
                    {titleCase(job.docType)}
                  </span>
                  <span className="shrink-0 text-[11px] text-text-faint tabular-nums">
                    {formatRelativeTime(job.startedAt ?? job.createdAt, now)}
                  </span>
                </li>
              ))}
            </ul>
          )}

          {queue && queue.stuck.length > 0 && (
            <div className="flex flex-col gap-2 rounded-lg border border-warn/30 bg-warn-soft p-3">
              <div className="flex items-start gap-2">
                <TriangleAlert size={14} strokeWidth={2} className="mt-0.5 shrink-0 text-warn" />
                <div className="min-w-0">
                  <p className="text-[12px] font-semibold text-warn">
                    {queue.stuck.length} document{queue.stuck.length === 1 ? '' : 's'} stuck in
                    processing
                  </p>
                  {/* This sentence is the panel's whole reason to exist. The
                      pipeline claims a row before it starts work, so a crash
                      leaves it here — and because chunk upserts key on
                      (document, index) and Qdrant point ids are derived from
                      content, re-running is genuinely safe rather than merely
                      probably safe. Saying so is what lets someone act. */}
                  <p className="mt-0.5 text-[11.5px] leading-relaxed text-warn/90">
                    Claimed before work started and never finished. Safe to re-run — chunk upserts
                    and Qdrant point ids are deterministic, so a repeat produces the same rows.
                  </p>
                </div>
              </div>

              <ul className="flex flex-col gap-1.5">
                {queue.stuck.map((document) => (
                  <li
                    key={`${document.docType}-${document.id}`}
                    className="flex items-center gap-3 rounded-lg border border-warn/20 bg-surface px-3 py-2"
                  >
                    <span className="min-w-0 flex-1 truncate text-[12.5px] text-text">
                      {document.title}
                    </span>
                    <span className="shrink-0 text-[11px] text-text-faint tabular-nums">
                      stuck {formatRelativeTime(document.since, now)}
                    </span>
                    <Button
                      size="sm"
                      onClick={() => onRerun(document.docType, document.id)}
                      loading={rerunningId === document.id}
                    >
                      Re-run
                    </Button>
                  </li>
                ))}
              </ul>
            </div>
          )}
        </div>
      </AsyncBoundary>
    </Panel>
  );
}
