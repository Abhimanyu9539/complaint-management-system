import { CopyableValue, Field, SectionLabel } from '@/components/admin/DrawerParts';
import { Drawer } from '@/components/ui/Drawer';
import { RunStatusPill, StatusPill } from '@/components/ui/StatusPill';
import { formatDuration, formatTimestamp, titleCase } from '@/lib/format';
import {
  TONE_CLASSES,
  agentNodeLabel,
  runTriggerLabel,
  ticketStatusLabel,
  ticketStatusTone,
} from '@/lib/status';
import type { AgentRun } from '@/lib/admin/types';

interface RunDrawerProps {
  run: AgentRun | null;
  onClose(): void;
}

export function RunDrawer({ run, onClose }: RunDrawerProps) {
  return (
    <Drawer
      open={run !== null}
      onClose={onClose}
      title={run?.ticketNo != null ? `T-${run.ticketNo} run` : 'Run'}
      actions={run && <RunStatusPill status={run.status} />}
    >
      {run && (
        <div className="flex flex-col gap-5">
          {run.subject && <p className="text-[12.5px] text-text-muted">{run.subject}</p>}
          <div className="flex flex-col gap-1.5">
            <Field label="Trigger" value={runTriggerLabel(run.trigger)} />
            <Field label="Started" value={formatTimestamp(run.startedAt)} />
            <Field label="Graph latency" value={formatDuration(run.latencyMs)} />
          </div>

          <section>
            <SectionLabel>Routing decisions</SectionLabel>
            <div className="flex flex-col gap-1.5">
              {routingDecisions(run).map(([label, value]) => (
                <Field key={label} label={label} value={value} />
              ))}
            </div>
            {run.outcome && (
              <div className="mt-3 flex items-center justify-between gap-3">
                <span className="text-[11px] text-text-faint">Gate</span>
                <StatusPill
                  label={ticketStatusLabel(run.outcome)}
                  tone={ticketStatusTone(run.outcome)}
                  dot={false}
                />
              </div>
            )}
            {run.reviewReasons.length > 0 && (
              <ul className="mt-2 list-disc pl-4 text-[12px] leading-relaxed text-text-muted">
                {run.reviewReasons.map((reason) => (
                  <li key={reason}>{reason}</li>
                ))}
              </ul>
            )}
          </section>

          <section>
            <SectionLabel>Node timeline</SectionLabel>
            <NodeWaterfall run={run} />
          </section>

          {Object.keys(run.errors).length > 0 && (
            <section>
              <SectionLabel>Errors</SectionLabel>
              <div className="flex flex-col gap-2 rounded-lg border border-danger/30 bg-danger-soft p-3">
                {Object.entries(run.errors).map(([stage, error]) => (
                  <p key={stage} className="text-[12px] break-words text-danger">
                    <span className="font-medium">{stage}:</span> {error}
                  </p>
                ))}
              </div>
            </section>
          )}

          <section>
            <SectionLabel>LangSmith run id</SectionLabel>
            <CopyableValue value={run.id} />
          </section>
        </div>
      )}
    </Drawer>
  );
}

/** One line per decision the graph made, in the order it made them. */
function routingDecisions(run: AgentRun): [string, string][] {
  const ran = new Set(run.steps.map((step) => step.node));

  let retrieval = 'Not reached';
  if (ran.has('ticket_no_match')) retrieval = 'No match — holding reply';
  else if (ran.has('draft_reply')) retrieval = 'Matched — reply drafted';
  else if (ran.has('find_precedents')) retrieval = 'Stopped — retrieval failed';

  let grounding = 'Not checked';
  if (run.grounded === true) grounding = run.regenerated ? 'Grounded after one retry' : 'Grounded';
  if (run.grounded === false) grounding = 'Still ungrounded after retry';

  const confidence = run.confidence !== null ? `${Math.round(run.confidence * 100)}%` : '—';
  const department = run.department ? `${titleCase(run.department)} · ${confidence}` : '—';

  return [
    ['Input guard', run.status === 'blocked' ? 'Blocked' : 'Allowed'],
    ['Department', department],
    ['Category', run.category ? titleCase(run.category) : '—'],
    ['Retrieval', retrieval],
    ['Past-case answers offered', String(run.precedentsOffered)],
    ['Grounding', grounding],
  ];
}

/**
 * Each node as a bar placed by its start offset, so the parallel branches
 * (classify ‖ analyze, the two retrievals) overlap and a retry shows twice.
 */
function NodeWaterfall({ run }: { run: AgentRun }) {
  if (run.steps.length === 0) {
    return (
      <p className="text-[12px] text-text-faint">No node timings: the graph failed before any node.</p>
    );
  }

  const runStart = Date.parse(run.startedAt);
  const offsets = run.steps.map((step) => Math.max(0, Date.parse(step.startedAt) - runStart));
  const total = Math.max(
    run.latencyMs ?? 0,
    ...run.steps.map((step, index) => offsets[index] + step.ms),
    1,
  );

  return (
    <ol className="flex flex-col gap-1.5">
      {run.steps.map((step, index) => {
        const left = Math.min(100, (offsets[index] / total) * 100);
        const width = Math.max(1, Math.min(100 - left, (step.ms / total) * 100));
        return (
          <li key={`${step.node}-${index}`} className="flex items-center gap-2">
            <span
              className={`w-[120px] shrink-0 truncate text-[11.5px] ${step.ok ? 'text-text-muted' : 'text-danger'}`}
            >
              {agentNodeLabel(step.node)}
            </span>
            <span className="relative h-2 min-w-0 flex-1 rounded-full bg-surface-2">
              <span
                className={`absolute inset-y-0 rounded-full ${TONE_CLASSES[step.ok ? 'accent' : 'danger'].dot}`}
                style={{ left: `${left}%`, width: `${width}%` }}
              />
            </span>
            <span className="w-[52px] shrink-0 text-right font-mono text-[11px] text-text-faint tabular-nums">
              {formatDuration(step.ms)}
            </span>
          </li>
        );
      })}
    </ol>
  );
}
