import { Fragment } from 'react';
import { AlertTriangle, RefreshCw, Send } from 'lucide-react';
import { TicketActions } from '@/components/tickets/TicketActions';
import type { DepartmentOption } from '@/lib/admin/types';
import type { Ticket, TicketDraft } from '@/lib/tickets/types';

interface DraftPaneProps {
  ticket: Ticket;
  draft: TicketDraft | null;
  onRefresh(): void;
  departments: DepartmentOption[];
  onEscalate(departmentId: string, note: string): Promise<void>;
  onResolve(note: string): Promise<void>;
  actionError: string | null;
  acting: boolean;
}

// `split` with a capture group keeps the markers: odd indices are the `[n]`s.
const MARKER_SPLIT = /(\[\d+\])/;

/** The draft text, with each `[n]` shown as a small superscript naming its source. */
function DraftText({ draft }: { draft: TicketDraft }) {
  const sources = new Map<number, string>([
    ...draft.policyRefs.map((ref) => [ref.marker, ref.section || ref.title] as const),
    ...draft.retrievedCases.map((item) => [item.marker, `Past case: ${item.title}`] as const),
  ]);

  return (
    <>
      {draft.draftText.split(MARKER_SPLIT).map((part, index) => {
        if (index % 2 === 0) return <Fragment key={index}>{part}</Fragment>;
        const marker = Number(part.slice(1, -1));
        return (
          <sup
            key={index}
            title={sources.get(marker) ?? 'Unknown source'}
            className="ml-px cursor-help font-mono text-[9.5px] text-accent"
          >
            {marker}
          </sup>
        );
      })}
    </>
  );
}

function CautionNote({ title, reasons = [] }: { title: string; reasons?: string[] }) {
  return (
    <div className="mb-2.5 flex items-start gap-2 rounded-lg border border-warn/30 bg-warn-soft px-3 py-2 text-[12px] leading-relaxed text-warn">
      <AlertTriangle size={14} strokeWidth={1.75} className="mt-0.5 shrink-0" />
      <div className="min-w-0">
        <p>{title}</p>
        {reasons.length > 0 && (
          <ul className="mt-1 list-disc pl-4">
            {reasons.map((reason) => (
              <li key={reason}>{reason}</li>
            ))}
          </ul>
        )}
      </div>
    </div>
  );
}

/**
 * The reply the ticket graph drafted for the customer. `[n]` markers stay in so
 * the operator can check each claim against the Evidence pane.
 *
 * "Send to customer" stays disabled: there is no send endpoint yet. Escalate and
 * Resolve below it are real, live actions on `ticket_service`'s state machine.
 */
export function DraftPane({
  ticket,
  draft,
  onRefresh,
  departments,
  onEscalate,
  onResolve,
  actionError,
  acting,
}: DraftPaneProps) {
  return (
    <div className="flex flex-col gap-4 p-4">
      <div>
        <h3 className="mb-2 text-[10px] font-semibold tracking-[0.08em] text-text-faint uppercase">
          Draft reply to customer
        </h3>

        {draft ? (
          <>
            {draft.noMatch && (
              <CautionNote title="No policy matched this complaint. This is a holding reply that only acknowledges it — write the resolution yourself or escalate." />
            )}
            {draft.grounded === false && (
              <CautionNote
                title="This draft failed the automated checks twice. Verify every claim against the evidence before using it:"
                reasons={draft.guardReasons}
              />
            )}
            <div className="rounded-lg border border-border bg-bg-elevated p-3.5 text-[12.5px] leading-relaxed whitespace-pre-wrap text-text">
              <DraftText draft={draft} />
            </div>
            <p className="mt-1.5 text-[11px] text-text-faint">
              Version {draft.version} · {draft.model} · prompt {draft.promptVersion}
            </p>
          </>
        ) : (
          <div className="rounded-lg border border-dashed border-border p-3.5 text-[12px] leading-relaxed text-text-muted">
            <p>
              No draft yet. Drafting runs in the background after the ticket arrives; if it
              failed, the timeline shows why.
            </p>
            <button
              type="button"
              onClick={onRefresh}
              className="mt-2 inline-flex h-7 items-center gap-1.5 rounded-lg border border-border bg-surface px-2.5 text-[11.5px] font-medium text-text hover:bg-surface-2"
            >
              <RefreshCw size={12} strokeWidth={2} />
              Check again
            </button>
          </div>
        )}

        <button
          type="button"
          disabled
          title="Disabled — sending is not built yet. The [n] markers are removed when it is."
          className="mt-2.5 inline-flex h-8 shrink-0 cursor-not-allowed items-center gap-1.5 rounded-lg border border-border bg-bg-elevated px-2.5 text-[12px] font-medium text-text-faint opacity-60"
        >
          <Send size={13} strokeWidth={2} />
          Send to customer
        </button>
      </div>

      <div className="border-t border-border pt-4">
        <h3 className="mb-2 text-[10px] font-semibold tracking-[0.08em] text-text-faint uppercase">
          Actions
        </h3>
        <TicketActions
          ticket={ticket}
          departments={departments}
          onEscalate={onEscalate}
          onResolve={onResolve}
          error={actionError}
          acting={acting}
        />
      </div>
    </div>
  );
}
