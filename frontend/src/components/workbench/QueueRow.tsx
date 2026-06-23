import { SeverityBadge } from '@/components/tickets/SeverityBadge';
import { formatRelativeTime } from '@/lib/format';
import type { Ticket } from '@/lib/tickets/types';

interface QueueRowProps {
  ticket: Ticket;
  active: boolean;
  onSelect(): void;
  departmentLabel(id: string | null): string;
}

/**
 * One queue row: a severity icon, subject, reference, department, and age.
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
      <span className="shrink-0 self-start pt-0.5">
        <SeverityBadge severity={ticket.severity} iconOnly />
      </span>
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
