import {
  TONE_CLASSES,
  confidenceTone,
  docStatusLabel,
  docStatusTone,
  isJobActive,
  jobStatusLabel,
  jobStatusTone,
  runStatusLabel,
  runStatusTone,
  type Tone,
} from '@/lib/status';
import type { AgentRunStatus, DocStatus, JobStatus } from '@/lib/admin/types';

interface StatusPillProps {
  label: string;
  tone: Tone;
  /** Leading dot. On by default — it is what makes an 11px pill readable at a glance. */
  dot?: boolean;
  /** Pulses the dot. Only for genuinely in-flight states, never for emphasis. */
  pulse?: boolean;
  title?: string;
}

/**
 * The status vocabulary of the whole panel, carried over from the workbench
 * prototype: a rounded pill with a 6px dot in the current colour.
 */
export function StatusPill({ label, tone, dot = true, pulse = false, title }: StatusPillProps) {
  const classes = TONE_CLASSES[tone];

  return (
    <span
      title={title}
      className={`inline-flex shrink-0 items-center gap-1.5 rounded-full px-2 py-0.5 text-[11px] font-semibold whitespace-nowrap ${classes.soft}`}
    >
      {dot && (
        <span
          aria-hidden="true"
          className={`h-1.5 w-1.5 shrink-0 rounded-full ${classes.dot}`}
          style={pulse ? { animation: 'pulse-soft 1.6s ease-in-out infinite' } : undefined}
        />
      )}
      {label}
    </span>
  );
}

/** An ingestion job's status. Pulses while queued or running. */
export function JobStatusPill({ status }: { status: JobStatus }) {
  return (
    <StatusPill
      label={jobStatusLabel(status)}
      tone={jobStatusTone(status)}
      pulse={isJobActive(status)}
    />
  );
}

/** A document's lifecycle state. */
export function DocStatusPill({ status }: { status: DocStatus }) {
  return (
    <StatusPill
      label={docStatusLabel(status)}
      tone={docStatusTone(status)}
      pulse={status === 'processing'}
    />
  );
}

/** An agent run's outcome. */
export function RunStatusPill({ status }: { status: AgentRunStatus }) {
  return (
    <StatusPill
      label={runStatusLabel(status)}
      tone={runStatusTone(status)}
      pulse={status === 'running'}
    />
  );
}

/**
 * A 0–1 confidence as a percentage, graded on the prototype's three tiers.
 *
 * Monospaced and tabular so a column of them lines up — comparing routing
 * confidence across rows is the only reason to show the number at all.
 */
export function ConfidenceChip({ value }: { value: number | null }) {
  if (value === null) {
    return <span className="text-[12px] text-text-faint">—</span>;
  }

  const tone = confidenceTone(value);
  return (
    <span
      title={
        value < 0.6
          ? 'Below the 0.60 routing threshold — this department is a guess.'
          : undefined
      }
      className={`inline-flex shrink-0 items-center rounded px-1.5 py-0.5 font-mono text-[11px] tabular-nums ${TONE_CLASSES[tone].soft}`}
    >
      {Math.round(value * 100)}%
    </span>
  );
}
