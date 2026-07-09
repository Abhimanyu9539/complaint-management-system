import { Timer } from 'lucide-react';
import { AsyncBoundary } from '@/components/ui/AsyncBoundary';
import { EmptyState } from '@/components/ui/EmptyState';
import { Panel } from '@/components/ui/Panel';
import { Skeleton } from '@/components/ui/Skeleton';
import { formatCount, formatDuration } from '@/lib/format';
import { TONE_CLASSES, agentNodeLabel } from '@/lib/status';
import type { AsyncData } from '@/hooks/useAsyncData';
import type { AgentSummary } from '@/lib/admin/types';

/** Median time per node over the window, slowest first. */
export function NodeLatencyPanel({ summary }: { summary: AsyncData<AgentSummary> }) {
  const nodes = summary.data?.nodeLatency ?? [];
  const slowest = Math.max(1, ...nodes.map((node) => node.p50Ms));

  return (
    <Panel
      title="Node latency"
      eyebrow={`Median, last ${summary.data?.rangeDays ?? 7} days`}
      description="Where a run spends its time. A node that ran twice in one run (a retry) counts twice."
    >
      <AsyncBoundary
        status={summary.status}
        error={summary.error}
        errorDetail={summary.errorDetail}
        failureCount={summary.failureCount}
        isEmpty={nodes.length === 0}
        onRetry={summary.refresh}
        empty={
          <EmptyState
            icon={<Timer size={18} strokeWidth={1.5} />}
            title="No node timings yet"
            description="Timings appear once the ticket graph has run in this window."
          />
        }
        skeleton={
          <div className="flex flex-col gap-2">
            {Array.from({ length: 6 }, (_, index) => (
              <Skeleton key={index} className="h-4" />
            ))}
          </div>
        }
      >
        <ol className="flex flex-col gap-2">
          {nodes.map((node) => (
            <li key={node.node} className="flex items-center gap-2">
              <span className="w-[128px] shrink-0 truncate text-[12px] text-text-muted">
                {agentNodeLabel(node.node)}
              </span>
              <span className="relative h-2 min-w-0 flex-1 rounded-full bg-surface-2">
                <span
                  className={`absolute inset-y-0 left-0 rounded-full ${TONE_CLASSES.accent.dot}`}
                  style={{ width: `${Math.max(1, (node.p50Ms / slowest) * 100)}%` }}
                />
              </span>
              <span className="w-[56px] shrink-0 text-right font-mono text-[11.5px] text-text tabular-nums">
                {formatDuration(node.p50Ms)}
              </span>
              <span className="w-[48px] shrink-0 text-right text-[11px] text-text-faint tabular-nums">
                ×{formatCount(node.samples)}
              </span>
            </li>
          ))}
        </ol>
      </AsyncBoundary>
    </Panel>
  );
}
