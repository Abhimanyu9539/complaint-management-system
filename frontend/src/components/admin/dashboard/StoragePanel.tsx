import { Database, TriangleAlert } from 'lucide-react';
import { AsyncBoundary } from '@/components/ui/AsyncBoundary';
import { EmptyState } from '@/components/ui/EmptyState';
import { Panel } from '@/components/ui/Panel';
import { Skeleton } from '@/components/ui/Skeleton';
import { StatusPill } from '@/components/ui/StatusPill';
import { usePanelData } from '@/hooks/usePanelData';
import { formatBytes, formatCount } from '@/lib/format';
import { adminTransport } from '@/lib/admin/transport';
import type { AsyncData } from '@/hooks/useAsyncData';
import type { StorageUsage } from '@/lib/admin/types';

type CollectionStatus = StorageUsage['collections'][number]['status'];

/** Qdrant's own collection health, mapped onto the panel's tones. */
function collectionTone(status: CollectionStatus) {
  if (status === 'green') return 'ok' as const;
  if (status === 'yellow') return 'warn' as const;
  if (status === 'red' || status === 'unknown') return 'danger' as const;
  // A collection that has not been created yet is a setup step, not a fault.
  if (status === 'missing') return 'warn' as const;
  return 'neutral' as const;
}

/**
 * What to do about it. `missing` and `unknown` look similar on a dashboard but
 * have completely different remedies, so each carries its own.
 */
function collectionRemedy(status: CollectionStatus): string | null {
  if (status === 'missing') return 'Collection not created yet — run `uv run cms-create-collections`.';
  if (status === 'unknown') return 'Qdrant could not be reached — check QDRANT_URL and /health/deps.';
  return null;
}

/**
 * Storage is exactly three measurable things, and no invented fourth.
 *
 * 1. Qdrant point counts per collection, with an explicitly-labelled byte
 *    *estimate* — Qdrant reports no byte figure.
 * 2. Supabase chunk-row counts, shown alongside the point counts because the
 *    drift between them is a real consistency signal.
 * 3. How many policy files are in Supabase Storage. A count, not a size: we
 *    cannot measure bytes without a Storage list call we do not make.
 */
export function StoragePanel() {
  // 2× the base cadence — this is the only panel that talks to Qdrant.
  const storage = usePanelData('storage', (signal) => adminTransport.getStorageUsage(signal), {
    intervalFactor: 2,
  });

  return (
    <Panel title="Storage" eyebrow="Vector store">
      <StorageBody storage={storage} />
    </Panel>
  );
}

function StorageBody({ storage }: { storage: AsyncData<StorageUsage> }) {
  const data = storage.data;

  const totalChunks = data ? data.chunkRows.caseChunks + data.chunkRows.policyChunks : 0;
  const totalPoints = data
    ? data.collections.reduce((sum, collection) => sum + collection.pointCount, 0)
    : 0;
  // Postgres is written before Qdrant, so chunks ahead of points is what an
  // interrupted upsert looks like. Points ahead of chunks means stale vectors.
  //
  // Only meaningful once every collection actually answered: a missing or
  // unreachable collection reports 0 points, which would otherwise be blamed on
  // an interrupted upsert and send someone looking for a bug that isn't there.
  const collectionsUsable =
    data?.collections.every(
      (collection) => collection.reachable && collection.status !== 'missing',
    ) ?? false;
  const drift = collectionsUsable ? totalChunks - totalPoints : 0;

  return (
    <AsyncBoundary
      status={storage.status}
      error={storage.error}
      errorDetail={storage.errorDetail}
      failureCount={storage.failureCount}
      isEmpty={!data || data.collections.length === 0}
      onRetry={storage.refresh}
      empty={
        <EmptyState
          icon={<Database size={18} strokeWidth={1.5} />}
          title="No collections found"
          description="Create them before ingesting anything."
        />
      }
      skeleton={
        <div className="flex flex-col gap-2">
          <Skeleton className="h-16" />
          <Skeleton className="h-16" />
        </div>
      }
    >
      {data && (
        <div className="flex flex-col gap-3">
          {data.collections.map((collection) => (
            <div
              key={collection.name}
              className="flex min-w-0 flex-col gap-1.5 rounded-lg border border-border bg-bg-elevated px-3 py-2.5"
            >
              <div className="flex items-center justify-between gap-2">
                <span className="min-w-0 truncate font-mono text-[12px] text-text">
                  {collection.name}
                </span>
                <StatusPill
                  label={collection.status === 'unknown' ? 'unreachable' : collection.status}
                  tone={collectionTone(collection.status)}
                />
              </div>

              {/* The remedy, not just the symptom. "missing" and "unreachable"
                  look alike on a dashboard and are fixed in entirely different
                  places. */}
              {collectionRemedy(collection.status) && (
                <p className="text-[11px] leading-relaxed text-warn">
                  {collectionRemedy(collection.status)}
                </p>
              )}

              <dl className="flex flex-wrap gap-x-4 gap-y-0.5 text-[11px]">
                <div className="flex gap-1">
                  <dt className="text-text-faint">Points</dt>
                  <dd className="font-medium text-text tabular-nums">
                    {formatCount(collection.pointCount)}
                  </dd>
                </div>
                <div className="flex gap-1">
                  <dt className="text-text-faint">Indexed</dt>
                  <dd className="font-medium text-text tabular-nums">
                    {formatCount(collection.indexedVectorCount)}
                  </dd>
                </div>
                <div className="flex gap-1">
                  <dt className="text-text-faint">Segments</dt>
                  <dd className="font-medium text-text tabular-nums">
                    {formatCount(collection.segmentCount)}
                  </dd>
                </div>
                <div className="flex gap-1">
                  <dt className="text-text-faint">Vectors</dt>
                  <dd
                    title={`Estimated as points × ${data.embeddingDims} dims × 4 bytes. Excludes payloads, sparse vectors and the HNSW graph, so treat it as a floor.`}
                    className="font-medium text-text tabular-nums"
                  >
                    est. {formatBytes(collection.estimatedVectorBytes)}
                  </dd>
                </div>
              </dl>
            </div>
          ))}

          <div className="flex flex-wrap items-center justify-between gap-2 border-t border-border pt-2.5 text-[11px]">
            <span className="text-text-muted">
              Chunk rows{' '}
              <span className="font-medium text-text tabular-nums">{formatCount(totalChunks)}</span>{' '}
              · Policy files{' '}
              <span className="font-medium text-text tabular-nums">
                {formatCount(data.storedPolicyFiles)}
              </span>
            </span>

            {drift !== 0 && (
              <span className="inline-flex items-center gap-1 rounded-full bg-warn-soft px-2 py-0.5 font-medium text-warn">
                <TriangleAlert size={11} strokeWidth={2} />
                {Math.abs(drift)} {drift > 0 ? 'chunk rows without vectors' : 'vectors without rows'}
              </span>
            )}
          </div>
        </div>
      )}
    </AsyncBoundary>
  );
}
