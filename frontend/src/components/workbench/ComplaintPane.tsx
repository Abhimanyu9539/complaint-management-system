import { SkeletonLines } from '@/components/ui/Skeleton';
import { StatusPill } from '@/components/ui/StatusPill';
import { SeverityBadge } from '@/components/tickets/SeverityBadge';
import { TicketTimeline } from '@/components/tickets/TicketTimeline';
import { formatTimestamp } from '@/lib/format';
import { ticketStatusLabel, ticketStatusTone } from '@/lib/status';
import type { TicketDetail, TicketEvent } from '@/lib/tickets/types';
import { ProgressTracker } from './ProgressTracker';

interface ComplaintPaneProps {
  detail: TicketDetail | null;
  loading: boolean;
  departmentLabel(id: string | null): string;
}

// The classifier's entity keys (backend `TicketEntities`), in display order.
const ENTITY_LABELS: Record<string, string> = {
  order_no: 'Order',
  invoice_no: 'Invoice',
  product: 'Product',
  amount: 'Amount',
  error_code: 'Error code',
};

// The audit events that carry a message: to or from a department, or a customer's reply.
const DEPT_EVENT_PREFIX: Record<string, string | undefined> = {
  escalated: 'Question to',
  dept_responded: 'Answer from',
  customer_replied: 'Reply from the customer',
};

// Where each message event keeps its text.
const MESSAGE_TEXT_KEY: Record<string, string> = {
  escalated: 'note',
  dept_responded: 'answer',
  customer_replied: 'text',
};

/** One message on the ticket, from the audit log. */
interface TicketMessage {
  id: number;
  label: string;
  text: string;
  at: string;
}

function ticketMessages(
  events: TicketEvent[],
  departmentLabel: (id: string | null) => string,
): TicketMessage[] {
  return events.flatMap((event) => {
    const prefix = DEPT_EVENT_PREFIX[event.event];
    if (!prefix) return [];
    const text = event.payload[MESSAGE_TEXT_KEY[event.event]];
    if (typeof text !== 'string' || !text.trim()) return [];

    const departmentId = event.payload.department_id;
    const label =
      event.event === 'customer_replied'
        ? prefix
        : `${prefix} ${departmentLabel(typeof departmentId === 'string' ? departmentId : null)}`;
    return [{ id: event.id, label, text, at: event.createdAt }];
  });
}

/**
 * The complaint itself: what the customer said, and where it has got to.
 *
 * The two things the user asked this page to show — the ticket's own facts,
 * and its progress — live here, fully backed by live data. Nothing in this
 * pane is simulated.
 */
export function ComplaintPane({ detail, loading, departmentLabel }: ComplaintPaneProps) {
  if (!detail) {
    return (
      <div className="flex flex-col gap-4 p-4">
        <SkeletonLines rows={2} />
        <SkeletonLines rows={5} />
      </div>
    );
  }

  const { ticket, events } = detail;
  const entityChips = Object.entries(ENTITY_LABELS).flatMap(([key, label]) =>
    ticket.entities[key] ? [[label, ticket.entities[key]] as const] : [],
  );
  const messages = ticketMessages(events, departmentLabel);

  return (
    <div className={`flex flex-col gap-5 p-4 ${loading ? 'opacity-60' : ''}`}>
      <div>
        <div className="mb-1 flex items-center gap-2">
          <span className="font-mono text-[11.5px] text-text-muted tabular-nums">
            T-{ticket.ticketNo}
          </span>
          <StatusPill label={ticketStatusLabel(ticket.status)} tone={ticketStatusTone(ticket.status)} />
          <SeverityBadge severity={ticket.severity} />
        </div>
        <h2 className="text-[15px] leading-snug font-semibold text-text">{ticket.subject}</h2>
        <p className="mt-1 text-[11.5px] text-text-faint">
          {ticket.customerEmail ?? 'No reply address'} · opened {formatTimestamp(ticket.createdAt)}
        </p>
      </div>

      <section>
        <h3 className="mb-1.5 text-[11px] font-semibold tracking-[0.08em] text-text-faint uppercase">
          Complaint
        </h3>
        {ticket.body ? (
          <p className="rounded-lg border border-border bg-bg-elevated px-3 py-2.5 text-[12.5px] leading-relaxed whitespace-pre-wrap text-text">
            {ticket.body}
          </p>
        ) : (
          <p className="text-[12px] text-text-faint">
            No body recorded. Tickets created before the web intake landed carry a subject only.
          </p>
        )}
        {entityChips.length > 0 && (
          <div className="mt-2 flex flex-wrap gap-1.5">
            {entityChips.map(([label, value]) => (
              <span
                key={label}
                className="rounded-full border border-border bg-surface px-2 py-0.5 text-[11px] text-text-muted"
              >
                {label} <b className="font-semibold text-text">{value}</b>
              </span>
            ))}
          </div>
        )}
      </section>

      {messages.length > 0 && (
        <section>
          <h3 className="mb-1.5 text-[11px] font-semibold tracking-[0.08em] text-text-faint uppercase">
            Messages
          </h3>
          <div className="flex flex-col gap-2">
            {messages.map((message) => (
              <div
                key={message.id}
                className="rounded-lg border border-dashed border-border bg-surface px-3 py-2.5"
              >
                <p className="mb-1 text-[11px] font-semibold tracking-[0.04em] text-text-muted uppercase">
                  {message.label} · {formatTimestamp(message.at)}
                </p>
                <p className="text-[12.5px] leading-relaxed whitespace-pre-wrap text-text">
                  {message.text}
                </p>
              </div>
            ))}
          </div>
        </section>
      )}

      <section>
        <h3 className="mb-2 text-[11px] font-semibold tracking-[0.08em] text-text-faint uppercase">
          Progress
        </h3>
        <ProgressTracker ticket={ticket} events={events} departmentLabel={departmentLabel} />
      </section>

      <details className="group">
        <summary className="cursor-pointer text-[11px] font-semibold tracking-[0.06em] text-text-faint uppercase hover:text-text-muted">
          Full event history ({events.length})
        </summary>
        <div className="mt-2.5">
          <TicketTimeline events={events} />
        </div>
      </details>
    </div>
  );
}
