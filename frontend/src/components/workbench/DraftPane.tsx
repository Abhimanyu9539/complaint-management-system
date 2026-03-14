import { Send } from 'lucide-react';
import { TicketActions } from '@/components/tickets/TicketActions';
import { MockBadge } from '@/components/ui/MockBadge';
import { simulatedDraft } from '@/lib/tickets/simulated';
import type { DepartmentOption } from '@/lib/admin/types';
import type { Ticket } from '@/lib/tickets/types';

interface DraftPaneProps {
  ticket: Ticket;
  departments: DepartmentOption[];
  onEscalate(departmentId: string, note: string): Promise<void>;
  onResolve(note: string): Promise<void>;
  actionError: string | null;
  acting: boolean;
}

/**
 * The AI-drafted reply — simulated, and structurally incapable of reaching a
 * customer: "Send to customer" is rendered disabled because no send endpoint
 * exists (there is no agent — `admin-api.md`, and no writer for `drafts`).
 *
 * Escalate and Resolve below it are real, live actions on `ticket_service`'s
 * state machine. They render outside the simulated banner's border on purpose
 * — the one place in this pane where a fake block and a real one sit side by
 * side, so the boundary between them has to be visible, not implied.
 */
export function DraftPane({
  ticket,
  departments,
  onEscalate,
  onResolve,
  actionError,
  acting,
}: DraftPaneProps) {
  const draft = simulatedDraft(ticket);

  return (
    <div className="flex flex-col gap-4 p-4">
      <div>
        <h3 className="mb-2 text-[10px] font-semibold tracking-[0.08em] text-text-faint uppercase">
          Draft reply to customer
        </h3>
        <MockBadge
          variant="banner"
          reason="Simulated. No classifier, retriever or drafter exists yet — this text is a deterministic fixture, not generated from this ticket by a model."
          className="mb-2.5"
        />
        <div className="rounded-lg border border-warn/30 bg-bg-elevated p-3.5 text-[12.5px] leading-relaxed whitespace-pre-wrap text-text">
          {draft.text}
        </div>
        <button
          type="button"
          disabled
          title="Disabled — no send endpoint exists. A simulated draft cannot reach a customer."
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
