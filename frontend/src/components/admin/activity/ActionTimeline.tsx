import { Check, Minus, X } from 'lucide-react';
import { formatDuration } from '@/lib/format';
import { TONE_CLASSES, agentActionLabel, agentActionTone } from '@/lib/status';
import type { AgentAction } from '@/lib/admin/types';

interface ActionTimelineProps {
  actions: AgentAction[];
  /** Total run latency, so each step's bar is scaled against the whole. */
  totalMs: number;
}

/**
 * The graph nodes a single run executed, in order.
 *
 * Each step gets a duration bar scaled to the run total, which is what turns a
 * list of node names into something you can read a bottleneck out of. The
 * attempt counter is rendered as `2/2` when a node repeated, making the graph's
 * loop guards (retrieval ≤ 2, regeneration ≤ 1) legible — otherwise a repeated
 * node just looks like a duplicated log line.
 */
export function ActionTimeline({ actions, totalMs }: ActionTimelineProps) {
  const safeTotal = Math.max(1, totalMs);
  const maxAttempts = new Map<string, number>();
  for (const action of actions) {
    maxAttempts.set(action.type, Math.max(maxAttempts.get(action.type) ?? 0, action.attempt));
  }

  return (
    <ol className="flex flex-col gap-2.5">
      {actions.map((action) => {
        const tone = agentActionTone(action.status);
        const share = (action.durationMs / safeTotal) * 100;
        const repeated = (maxAttempts.get(action.type) ?? 1) > 1;

        return (
          <li key={action.id} className="flex min-w-0 gap-2.5">
            <span
              aria-hidden="true"
              className={`mt-0.5 flex h-4 w-4 shrink-0 items-center justify-center rounded-full ${TONE_CLASSES[tone].soft}`}
            >
              {action.status === 'ok' ? (
                <Check size={10} strokeWidth={3} />
              ) : action.status === 'failed' ? (
                <X size={10} strokeWidth={3} />
              ) : (
                <Minus size={10} strokeWidth={3} />
              )}
            </span>

            <div className="min-w-0 flex-1">
              <div className="flex items-baseline justify-between gap-2">
                <span className="min-w-0 truncate text-[12.5px] font-medium text-text">
                  {agentActionLabel(action.type)}
                  {repeated && (
                    <span
                      title="Loop guard: this node ran more than once before the graph moved on."
                      className="ml-1.5 font-mono text-[10.5px] font-normal text-text-faint tabular-nums"
                    >
                      {action.attempt}/{maxAttempts.get(action.type)}
                    </span>
                  )}
                </span>
                <span className="shrink-0 font-mono text-[11px] text-text-faint tabular-nums">
                  {formatDuration(action.durationMs)}
                </span>
              </div>

              <p className="mt-0.5 text-[11.5px] leading-relaxed text-text-muted">
                {action.detail}
              </p>

              <div className="mt-1 h-1 w-full overflow-hidden rounded-full bg-surface-2">
                <div
                  className={`h-full rounded-full ${TONE_CLASSES[tone].dot}`}
                  // Floored at 1% so a sub-millisecond step is still visible as
                  // a step rather than vanishing into the track.
                  style={{ width: `${Math.max(1, share)}%` }}
                />
              </div>
            </div>
          </li>
        );
      })}
    </ol>
  );
}
