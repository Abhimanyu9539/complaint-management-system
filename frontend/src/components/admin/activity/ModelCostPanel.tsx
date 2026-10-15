import { CircleDollarSign } from 'lucide-react';
import { AsyncBoundary } from '@/components/ui/AsyncBoundary';
import { EmptyState } from '@/components/ui/EmptyState';
import { Panel } from '@/components/ui/Panel';
import { Skeleton } from '@/components/ui/Skeleton';
import { formatCount, formatCurrency } from '@/lib/format';
import { TONE_CLASSES } from '@/lib/status';
import type { AsyncData } from '@/hooks/useAsyncData';
import type { AgentSummary } from '@/lib/admin/types';

/** LLM spend per model over the window, most expensive first. */
export function ModelCostPanel({ summary }: { summary: AsyncData<AgentSummary> }) {
  const models = summary.data?.costByModel ?? [];
  const highest = Math.max(Number.EPSILON, ...models.map((model) => model.costUsd));

  return (
    <Panel
      title="Model cost"
      eyebrow={`${formatCurrency(summary.data?.costUsd)}, last ${summary.data?.rangeDays ?? 7} days`}
      description="What OpenRouter billed for the ticket graph's calls. NeMo's rail calls report tokens only."
    >
      <AsyncBoundary
        status={summary.status}
        error={summary.error}
        errorDetail={summary.errorDetail}
        failureCount={summary.failureCount}
        isEmpty={models.length === 0}
        onRetry={summary.refresh}
        empty={
          <EmptyState
            icon={<CircleDollarSign size={18} strokeWidth={1.5} />}
            title="No model calls yet"
            description="Cost appears once the ticket graph has run in this window."
          />
        }
        skeleton={
          <div className="flex flex-col gap-2">
            {Array.from({ length: 3 }, (_, index) => (
              <Skeleton key={index} className="h-4" />
            ))}
          </div>
        }
      >
        <ol className="flex flex-col gap-2">
          {models.map((model) => (
            <li key={model.model} className="flex items-center gap-2">
              <span
                className="w-[128px] shrink-0 truncate font-mono text-[11.5px] text-text-muted"
                title={model.model}
              >
                {model.model}
              </span>
              <span className="relative h-2 min-w-0 flex-1 rounded-full bg-surface-2">
                <span
                  className={`absolute inset-y-0 left-0 rounded-full ${TONE_CLASSES.accent.dot}`}
                  style={{ width: `${Math.max(1, (model.costUsd / highest) * 100)}%` }}
                />
              </span>
              <span className="w-[64px] shrink-0 text-right font-mono text-[11.5px] text-text tabular-nums">
                {formatCurrency(model.costUsd)}
              </span>
              <span
                className="w-[88px] shrink-0 text-right text-[11px] text-text-faint tabular-nums"
                title={`${formatCount(model.inputTokens)} in / ${formatCount(model.outputTokens)} out`}
              >
                ×{formatCount(model.calls)} ·{' '}
                {formatCount(model.inputTokens + model.outputTokens)} tok
              </span>
            </li>
          ))}
        </ol>
      </AsyncBoundary>
    </Panel>
  );
}
