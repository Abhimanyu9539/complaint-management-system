import { Check, TriangleAlert } from 'lucide-react';
import { formatTimestamp } from '@/lib/format';
import { buildProgress, type ProgressStepState } from '@/lib/tickets/progress';
import type { Ticket, TicketEvent } from '@/lib/tickets/types';

const STEP_CAPTION: Record<ProgressStepState, string | null> = {
  done: null, // filled in per-step from its timestamp
  current: 'In progress',
  skipped: 'Not reached',
  pending: 'Pending',
};

/**
 * "Where the progress is till now" — the derived six-stage tracker.
 *
 * Every checkmark traces back to a `ticket_events` row (see
 * `lib/tickets/progress`); nothing here is inferred from `ticket.status`
 * alone. Most tickets today show real gaps — Classified and Drafted stay
 * un-ticked — because no classifier or drafter exists yet. That gap is the
 * truth, not a rendering bug.
 */
export function ProgressTracker({ ticket, events }: { ticket: Ticket; events: TicketEvent[] }) {
  const { steps, failed } = buildProgress(ticket, events);

  return (
    <div className="flex flex-col gap-1">
      {failed && (
        <p className="mb-2 flex items-center gap-1.5 rounded-lg border border-danger/30 bg-danger-soft px-2.5 py-2 text-[11.5px] font-medium text-danger">
          <TriangleAlert size={13} strokeWidth={2} className="shrink-0" />
          Processing failed — this ticket fell off the pipeline rather than completing a stage.
        </p>
      )}
      <ol className="flex flex-col gap-0">
        {steps.map((step, index) => (
          <li key={step.id} className="flex gap-2.5">
            <div className="flex w-4 shrink-0 flex-col items-center">
              <StepDot state={step.state} />
              {index < steps.length - 1 && (
                <span
                  className={`w-px flex-1 ${step.state === 'done' ? 'bg-accent' : 'bg-border'}`}
                />
              )}
            </div>
            <div className="min-w-0 flex-1 pb-3.5">
              <p
                className={`text-[12.5px] font-medium ${
                  step.state === 'pending' || step.state === 'skipped'
                    ? 'text-text-faint'
                    : 'text-text'
                }`}
              >
                {step.label}
              </p>
              <p className="text-[11px] text-text-faint">
                {step.state === 'done'
                  ? (step.at ? formatTimestamp(step.at) : 'Done')
                  : STEP_CAPTION[step.state]}
              </p>
            </div>
          </li>
        ))}
      </ol>
    </div>
  );
}

function StepDot({ state }: { state: ProgressStepState }) {
  if (state === 'done') {
    return (
      <span className="mt-0.5 flex h-4 w-4 shrink-0 items-center justify-center rounded-full bg-accent text-accent-text">
        <Check size={10} strokeWidth={3} />
      </span>
    );
  }
  if (state === 'current') {
    return (
      <span
        className="mt-1.25 h-2.5 w-2.5 shrink-0 rounded-full bg-accent"
        style={{ animation: 'pulse-soft 1.6s ease-in-out infinite' }}
      />
    );
  }
  return (
    <span
      className={`mt-1.25 h-2.5 w-2.5 shrink-0 rounded-full border-2 ${
        state === 'skipped' ? 'border-border-strong' : 'border-border'
      }`}
    />
  );
}
