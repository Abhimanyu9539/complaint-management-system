import { FileText } from 'lucide-react';
import { AsyncBoundary } from '@/components/ui/AsyncBoundary';
import { EmptyState } from '@/components/ui/EmptyState';
import { Panel } from '@/components/ui/Panel';
import { Skeleton } from '@/components/ui/Skeleton';
import { StackedBar } from '@/components/charts/StackedBar';
import { DOC_STATUS_ORDER, TONE_CLASSES, docStatusLabel, docStatusTone } from '@/lib/status';
import type { AsyncData } from '@/hooks/useAsyncData';
import type { AdminOverview, DocumentCounts } from '@/lib/admin/types';

/** Turns a status→count map into stacked-bar segments, in a fixed reading order. */
function toSegments(counts: DocumentCounts) {
  return DOC_STATUS_ORDER.map((status) => ({
    key: status,
    label: docStatusLabel(status),
    value: counts.byStatus[status] ?? 0,
    className: TONE_CLASSES[docStatusTone(status)].dot,
  }));
}

export function DocumentCountsPanel({ overview }: { overview: AsyncData<AdminOverview> }) {
  const documents = overview.data?.documents;

  return (
    <Panel title="Documents" eyebrow="Corpus">
      <AsyncBoundary
        status={overview.status}
        error={overview.error}
        errorDetail={overview.errorDetail}
        failureCount={overview.failureCount}
        isEmpty={!documents}
        onRetry={overview.refresh}
        empty={
          <EmptyState
            icon={<FileText size={18} strokeWidth={1.5} />}
            title="No documents indexed"
            description="Seed the corpus to populate the retrieval collections."
          />
        }
        skeleton={
          <div className="flex flex-col gap-5">
            <Skeleton className="h-14" />
            <Skeleton className="h-14" />
          </div>
        }
      >
        {documents && (
          <div className="flex flex-col gap-5">
            {(
              [
                ['Cases', documents.cases],
                ['Policies', documents.policies],
              ] as const
            ).map(([label, counts]) => (
              <div key={label} className="flex min-w-0 flex-col gap-2">
                <div className="flex items-baseline justify-between gap-2">
                  <span className="text-[12px] font-medium text-text">{label}</span>
                  <span className="text-[12px] text-text-muted tabular-nums">
                    <span className="font-semibold text-text">{counts.byStatus.indexed ?? 0}</span>{' '}
                    of {counts.total} indexed
                  </span>
                </div>
                <StackedBar segments={toSegments(counts)} />
              </div>
            ))}
          </div>
        )}
      </AsyncBoundary>
    </Panel>
  );
}
