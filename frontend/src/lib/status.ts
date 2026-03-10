/**
 * Status vocabulary and the status → colour mapping for the whole admin panel.
 *
 * This lives in `lib/` rather than beside `StatusPill` because oxlint's
 * `react/only-export-components` forbids a component module from exporting
 * helper *functions*. Keeping the mappings here also means the tables, the
 * charts and the pills cannot drift apart on what "failed" looks like.
 */

import type {
  AgentActionType,
  AgentRunStatus,
  DocStatus,
  JobStatus,
} from '@/lib/admin/types';
import type { ResolutionPath, TicketSeverity, TicketStatus } from '@/lib/tickets/types';

/**
 * The visual vocabulary. `neutral` is not an absence of meaning — it is the
 * honest rendering for a state that has not happened yet (queued, pending).
 *
 * The rule that decides which of these a chart series gets:
 *
 * > A series encoding a **quantity** follows the palette (`accent`, or
 * > `QUANTITY_SERIES` below). A series encoding a **status** stays on the
 * > semantic ramp (`ok` / `warn` / `info` / `danger`).
 *
 * The ramp is deliberately palette-independent — "failed" has to read red in
 * all six palettes or the colour stops carrying information. The cost of that
 * is that a quantity painted with a ramp token looks *stuck*: the user changes
 * palette and the chart stays green. Throughput, counts and volumes are not
 * statuses, and must not borrow status colours.
 */
export type Tone = 'neutral' | 'accent' | 'ok' | 'warn' | 'info' | 'danger';

interface ToneClasses {
  /** Soft background + readable foreground. Pills, chips, callout blocks. */
  soft: string;
  /** Foreground only. Icons and numbers sitting on the page background. */
  text: string;
  /** Solid fill. Chart bars and the dot inside a pill. */
  dot: string;
  /** SVG stroke utility for chart series. */
  stroke: string;
  /** SVG / element fill utility for chart marks. */
  fill: string;
}

/**
 * Complete literal class strings, never interpolated.
 *
 * Tailwind's scanner reads source text, so a template literal like
 * `bg-${tone}-soft` produces a class that was never compiled and silently
 * renders unstyled. Every variant has to appear verbatim somewhere in the
 * source — this table is that somewhere.
 */
export const TONE_CLASSES: Record<Tone, ToneClasses> = {
  neutral: {
    soft: 'bg-surface-2 text-text-muted',
    text: 'text-text-muted',
    dot: 'bg-text-faint',
    stroke: 'stroke-text-faint',
    fill: 'fill-text-faint',
  },
  accent: {
    soft: 'bg-accent-soft text-accent',
    text: 'text-accent',
    dot: 'bg-accent',
    stroke: 'stroke-accent',
    fill: 'fill-accent',
  },
  ok: {
    soft: 'bg-ok-soft text-ok',
    text: 'text-ok',
    dot: 'bg-ok',
    stroke: 'stroke-ok',
    fill: 'fill-ok',
  },
  warn: {
    soft: 'bg-warn-soft text-warn',
    text: 'text-warn',
    dot: 'bg-warn',
    stroke: 'stroke-warn',
    fill: 'fill-warn',
  },
  info: {
    soft: 'bg-info-soft text-info',
    text: 'text-info',
    dot: 'bg-info',
    stroke: 'stroke-info',
    fill: 'fill-info',
  },
  danger: {
    soft: 'bg-danger-soft text-danger',
    text: 'text-danger',
    dot: 'bg-danger',
    stroke: 'stroke-danger',
    fill: 'fill-danger',
  },
};

/**
 * A palette-following ramp for charts with several *quantity* series.
 *
 * One hue at descending opacity rather than several hues. Reaching for
 * `info`/`warn` to separate a second series is what this exists to prevent:
 * those tokens mean something, they do not change with the palette, and a
 * "storage volume" bar painted `bg-info` reads as a status to anyone who has
 * learned the rest of the panel.
 *
 * Index with `QUANTITY_SERIES[i % QUANTITY_SERIES.length]` so an unbounded
 * number of series degrades to repetition rather than to `undefined`. Past four
 * the opacities stop being reliably distinguishable — that is a signal the
 * chart wants a different shape, not a fifth entry here.
 *
 * Literal strings, same reason as `TONE_CLASSES`. Tailwind v4 compiles the
 * `/nn` modifier on a var-backed colour to `color-mix()`, which resolves at
 * paint time and so tracks the palette like any other accent utility.
 */
export const QUANTITY_SERIES = [
  { stroke: 'stroke-accent', fill: 'fill-accent', dot: 'bg-accent' },
  { stroke: 'stroke-accent/65', fill: 'fill-accent/65', dot: 'bg-accent/65' },
  { stroke: 'stroke-accent/40', fill: 'fill-accent/40', dot: 'bg-accent/40' },
  { stroke: 'stroke-accent/25', fill: 'fill-accent/25', dot: 'bg-accent/25' },
] as const;

/** `QUANTITY_SERIES` entry for series `index`, wrapping past the end. */
export function quantitySeries(index: number) {
  return QUANTITY_SERIES[index % QUANTITY_SERIES.length];
}

// ---------------------------------------------------------------------------
// Ingestion jobs
// ---------------------------------------------------------------------------

const JOB_TONES: Record<JobStatus, Tone> = {
  queued: 'neutral',
  running: 'accent',
  done: 'ok',
  failed: 'danger',
};

const JOB_LABELS: Record<JobStatus, string> = {
  queued: 'Queued',
  running: 'Running',
  done: 'Done',
  failed: 'Failed',
};

export function jobStatusTone(status: JobStatus): Tone {
  return JOB_TONES[status] ?? 'neutral';
}

export function jobStatusLabel(status: JobStatus): string {
  return JOB_LABELS[status] ?? status;
}

/** Job states that are still in flight — drives the pulsing dot and the queue. */
export function isJobActive(status: JobStatus): boolean {
  return status === 'queued' || status === 'running';
}

// ---------------------------------------------------------------------------
// Document lifecycle
// ---------------------------------------------------------------------------

const DOC_TONES: Record<DocStatus, Tone> = {
  pending: 'neutral',
  processing: 'accent',
  indexed: 'ok',
  failed: 'danger',
  // Deleting is a transient teardown state, not a failure — warn, not danger.
  deleting: 'warn',
};

const DOC_LABELS: Record<DocStatus, string> = {
  pending: 'Pending',
  processing: 'Processing',
  indexed: 'Indexed',
  failed: 'Failed',
  deleting: 'Deleting',
};

export function docStatusTone(status: DocStatus): Tone {
  return DOC_TONES[status] ?? 'neutral';
}

export function docStatusLabel(status: DocStatus): string {
  return DOC_LABELS[status] ?? status;
}

/** Render order for stacked bars and count tables — best outcome first. */
export const DOC_STATUS_ORDER: readonly DocStatus[] = [
  'indexed',
  'processing',
  'pending',
  'failed',
  'deleting',
];

export const JOB_STATUS_ORDER: readonly JobStatus[] = ['done', 'running', 'queued', 'failed'];

// ---------------------------------------------------------------------------
// Tickets
// ---------------------------------------------------------------------------

const TICKET_TONES: Record<TicketStatus, Tone> = {
  new: 'accent',
  processing: 'accent',
  drafted: 'info',
  needs_review: 'warn',
  /**
   * `warn`, not `danger`. An escalation is the system working as designed —
   * cms.md wants the *rate* pushed down, but an individual ticket that needed a
   * specialist is not a fault, and colouring it red would train an operator to
   * treat correct behaviour as breakage. Amber says "this one costs more".
   */
  escalated: 'warn',
  dept_responded: 'info',
  resolved: 'ok',
  processing_failed: 'danger',
};

const TICKET_LABELS: Record<TicketStatus, string> = {
  new: 'New',
  processing: 'Processing',
  drafted: 'Drafted',
  needs_review: 'Needs review',
  escalated: 'Escalated',
  dept_responded: 'Dept replied',
  resolved: 'Resolved',
  processing_failed: 'Failed',
};

export function ticketStatusTone(status: TicketStatus): Tone {
  return TICKET_TONES[status] ?? 'neutral';
}

export function ticketStatusLabel(status: TicketStatus): string {
  return TICKET_LABELS[status] ?? status;
}

/** Funnel order — earliest lifecycle state first, terminal states last. */
export const TICKET_STATUS_ORDER: readonly TicketStatus[] = [
  'new',
  'processing',
  'drafted',
  'needs_review',
  'escalated',
  'dept_responded',
  'resolved',
  'processing_failed',
];

/**
 * Severity is an ordered scale, so it gets a ramp rather than arbitrary hues.
 * `normal` is deliberately neutral: it is the default and the majority, and
 * colouring the common case makes the uncommon ones harder to spot.
 */
const SEVERITY_TONES: Record<TicketSeverity, Tone> = {
  low: 'neutral',
  normal: 'neutral',
  high: 'warn',
  critical: 'danger',
};

const SEVERITY_LABELS: Record<TicketSeverity, string> = {
  low: 'Low',
  normal: 'Normal',
  high: 'High',
  critical: 'Critical',
};

export function severityTone(severity: TicketSeverity): Tone {
  return SEVERITY_TONES[severity] ?? 'neutral';
}

export function severityLabel(severity: TicketSeverity): string {
  return SEVERITY_LABELS[severity] ?? severity;
}

/**
 * Path A / Path B (cms.md §1.2).
 *
 * A genuine status split, so both sides stay on the semantic ramp and neither
 * follows the palette — see the rule on `Tone`. `escalated` is `warn` rather
 * than `danger` for the same reason as the status above.
 */
export function resolutionPathTone(path: ResolutionPath): Tone {
  return path === 'escalated' ? 'warn' : 'ok';
}

// ---------------------------------------------------------------------------
// Agent runs
// ---------------------------------------------------------------------------

const RUN_TONES: Record<AgentRunStatus, Tone> = {
  running: 'accent',
  succeeded: 'ok',
  failed: 'danger',
  /**
   * Deliberately `info`, not `danger`. A run that correctly declined to answer
   * because nothing cleared the retrieval threshold did its job — colouring it
   * red would train operators to treat honest abstention as breakage.
   */
  no_match: 'info',
};

const RUN_LABELS: Record<AgentRunStatus, string> = {
  running: 'Running',
  succeeded: 'Succeeded',
  failed: 'Failed',
  no_match: 'No match',
};

export function runStatusTone(status: AgentRunStatus): Tone {
  return RUN_TONES[status] ?? 'neutral';
}

export function runStatusLabel(status: AgentRunStatus): string {
  return RUN_LABELS[status] ?? status;
}

/** Human labels for the RAG graph's nodes (lld.md §6). */
const ACTION_LABELS: Record<AgentActionType, string> = {
  analyze_query: 'Analyze query',
  direct_answer: 'Direct answer',
  retrieve: 'Retrieve',
  grade_documents: 'Grade documents',
  rewrite_query: 'Rewrite query',
  generate: 'Generate',
  check_groundedness: 'Check groundedness',
  no_match_response: 'No-match response',
};

export const AGENT_ACTION_TYPES = Object.keys(ACTION_LABELS) as AgentActionType[];

export function agentActionLabel(type: AgentActionType): string {
  return ACTION_LABELS[type] ?? type;
}

export function agentActionTone(status: 'ok' | 'failed' | 'skipped'): Tone {
  if (status === 'failed') return 'danger';
  if (status === 'skipped') return 'neutral';
  return 'ok';
}

// ---------------------------------------------------------------------------
// Confidence
// ---------------------------------------------------------------------------

/**
 * The prototype's three-tier rule, kept verbatim so the admin panel and the
 * agent workbench grade confidence identically. The 0.60 boundary is the
 * backend's `dept_confidence_threshold` default — below it, routing is a guess.
 */
export function confidenceTone(confidence: number): Tone {
  if (confidence >= 0.8) return 'ok';
  if (confidence >= 0.6) return 'warn';
  return 'danger';
}

/** Health of a whole subsystem, as reported by /health/deps. */
export function healthTone(status: 'ok' | 'degraded' | 'down' | 'error'): Tone {
  if (status === 'ok') return 'ok';
  if (status === 'degraded') return 'warn';
  return 'danger';
}
