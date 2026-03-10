import { Search } from 'lucide-react';
import { ActionTimeline } from './ActionTimeline';
import { ConfidenceChip, RunStatusPill } from '@/components/ui/StatusPill';
import { Drawer } from '@/components/ui/Drawer';
import { formatCount, formatCurrency, formatDuration, formatTimestamp } from '@/lib/format';
import { departmentLabel } from '@/lib/admin/mockTransport';
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
      title={run ? `Run ${run.id}` : 'Run'}
      actions={run && <RunStatusPill status={run.status} />}
    >
      {run && (
        <div className="flex flex-col gap-5">
          <section>
            <SectionLabel>Question</SectionLabel>
            <p className="rounded-lg border border-border bg-surface-2 px-3 py-2 text-[12.5px] leading-relaxed text-text">
              {run.inputSummary}
            </p>
          </section>

          {run.status === 'no_match' && (
            // The honest-uncertainty block. A run that declined to answer is a
            // correct outcome, and naming the threshold it failed to clear is
            // what makes it reviewable instead of just disappointing.
            <div className="flex items-start gap-2 rounded-lg border border-info/30 bg-info-soft px-3 py-2.5">
              <Search size={14} strokeWidth={2} className="mt-0.5 shrink-0 text-info" />
              <div className="min-w-0">
                <p className="text-[12px] font-semibold text-info">Nothing cleared the threshold</p>
                <p className="mt-0.5 text-[11.5px] leading-relaxed text-info/90">
                  No source scored above the 0.60 department-confidence threshold
                  {run.confidence !== null && (
                    <> — the best candidate reached {Math.round(run.confidence * 100)}%</>
                  )}
                  . The graph returned a holding response rather than an unsupported answer.
                </p>
              </div>
            </div>
          )}

          {run.outputSummary && (
            <section>
              <SectionLabel>Answer</SectionLabel>
              <p className="text-[12.5px] leading-relaxed text-text-muted">{run.outputSummary}</p>
            </section>
          )}

          <section>
            <SectionLabel>Graph execution</SectionLabel>
            <ActionTimeline actions={run.actions} totalMs={run.totalLatencyMs ?? 0} />
          </section>

          <section>
            <SectionLabel>Routing</SectionLabel>
            <div className="flex items-center gap-2">
              <span className="text-[12.5px] text-text">{departmentLabel(run.department)}</span>
              <ConfidenceChip value={run.confidence} />
            </div>
          </section>

          <section>
            <SectionLabel>Cost and latency</SectionLabel>
            <dl className="grid grid-cols-2 gap-x-4 gap-y-1.5">
              <Row label="Total latency" value={formatDuration(run.totalLatencyMs)} />
              <Row label="Cost" value={formatCurrency(run.costUsd)} />
              <Row label="Input tokens" value={formatCount(run.inputTokens)} />
              <Row label="Output tokens" value={formatCount(run.outputTokens)} />
            </dl>
          </section>

          <section>
            <SectionLabel>Metadata</SectionLabel>
            <dl className="flex flex-col gap-1.5">
              <Row label="Started" value={formatTimestamp(run.startedAt)} />
              <Row label="Finished" value={formatTimestamp(run.finishedAt)} />
              <Row label="Session" value={run.sessionId ?? '—'} mono />
              <Row label="LangSmith run" value={run.langsmithRunId ?? '—'} mono />
            </dl>
          </section>
        </div>
      )}
    </Drawer>
  );
}

function SectionLabel({ children }: { children: string }) {
  return (
    <h3 className="mb-2 text-[10px] font-semibold tracking-[0.08em] text-text-faint uppercase">
      {children}
    </h3>
  );
}

function Row({ label, value, mono = false }: { label: string; value: string; mono?: boolean }) {
  return (
    <div className="flex min-w-0 items-baseline justify-between gap-3">
      <dt className="shrink-0 text-[11px] text-text-faint">{label}</dt>
      <dd
        className={`min-w-0 truncate text-[12px] tabular-nums ${mono ? 'font-mono text-text-muted' : 'text-text'}`}
      >
        {value}
      </dd>
    </div>
  );
}
