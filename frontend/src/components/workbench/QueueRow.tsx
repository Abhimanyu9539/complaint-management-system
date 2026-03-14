import { formatRelativeTime } from '@/lib/format';
import type { Ticket, TicketSeverity } from '@/lib/tickets/types';

interface QueueRowProps {
  ticket: Ticket;
  active: boolean;
  onSelect(): void;
  departmentLabel(id: string | null): string;
}

/** Complete literal classes — the status group heading already carries status colour. */
const SEVERITY_SPINE: Record<TicketSeverity, string> = {
  low: 'bg-transparent',
  normal: 'bg-transparent',
  high: 'bg-warn',
  critical: 'bg-danger',
};

/**
 * One queue row: a severity spine, subject, reference, department, and age.
 *
 * No status pill here — the row lives inside a status group heading, and
 * repeating the status on every row it already labels would be noise, unlike
 * `/admin/tickets`'s flat table, which has no such heading to lean on.
 */
export function QueueRow({ ticket, active, onSelect, departmentLabel }: QueueRowProps) {
  return (
    <button
      type="button"
      onClick={onSelect}
      aria-current={active || undefined}
      className={`flex w-full items-stretch gap-2.5 rounded-lg border px-2.5 py-2 text-left transition-colors ${
        active
          ? 'border-accent bg-accent-soft'
          : 'border-transparent hover:bg-surface-hover'
      }`}
    >
      <span
        aria-hidden="true"
        className={`w-[3px] shrink-0 rounded-full ${SEVERITY_SPINE[ticket.severity]}`}
      />
      <span className="min-w-0 flex-1">
        <span className="block truncate text-[12.5px] font-medium text-text">
          {ticket.subject}
        </span>
        <span className="mt-0.5 flex items-center gap-1.5 text-[11px] text-text-faint">
          <span className="font-mono tabular-nums">T-{ticket.ticketNo}</span>
          {ticket.escalatedDept ? (
            <span className="min-w-0 truncate text-text-muted">
              {departmentLabel(ticket.escalatedDept)}
            </span>
          ) : ticket.predictedDept ? (
            <span className="min-w-0 truncate italic">
              {departmentLabel(ticket.predictedDept)}?
            </span>
          ) : null}
        </span>
      </span>
      <span className="shrink-0 self-start pt-0.5 text-[10.5px] text-text-faint tabular-nums">
        {formatRelativeTime(ticket.createdAt)}
      </span>
    </button>
  );
}
