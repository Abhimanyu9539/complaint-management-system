import { SkeletonLines } from '@/components/ui/Skeleton';
import { StatusPill } from '@/components/ui/StatusPill';
import { TicketTimeline } from '@/components/tickets/TicketTimeline';
import { formatTimestamp } from '@/lib/format';
import { severityLabel, severityTone, ticketStatusLabel, ticketStatusTone } from '@/lib/status';
import type { TicketDetail } from '@/lib/tickets/types';
import { ProgressTracker } from './ProgressTracker';

interface ComplaintPaneProps {
  detail: TicketDetail | null;
  loading: boolean;
}

// The classifier's entity keys (backend `TicketEntities`), in display order.
const ENTITY_LABELS: Record<string, string> = {
  order_no: 'Order',
  invoice_no: 'Invoice',
  product: 'Product',
  amount: 'Amount',
  error_code: 'Error code',
};

/**
 * The complaint itself: what the customer said, and where it has got to.
 *
 * The two things the user asked this page to show — the ticket's own facts,
 * and its progress — live here, fully backed by live data. Nothing in this
 * pane is simulated.
 */
export function ComplaintPane({ detail, loading }: ComplaintPaneProps) {
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

  return (
    <div className={`flex flex-col gap-5 p-4 ${loading ? 'opacity-60' : ''}`}>
      <div>
        <div className="mb-1 flex items-center gap-2">
          <span className="font-mono text-[11.5px] text-text-muted tabular-nums">
            T-{ticket.ticketNo}
          </span>
          <StatusPill label={ticketStatusLabel(ticket.status)} tone={ticketStatusTone(ticket.status)} />
          <StatusPill label={severityLabel(ticket.severity)} tone={severityTone(ticket.severity)} />
        </div>
        <h2 className="text-[15px] leading-snug font-semibold text-text">{ticket.subject}</h2>
        <p className="mt-1 text-[11.5px] text-text-faint">
          {ticket.customerEmail ?? 'No reply address'} · opened {formatTimestamp(ticket.createdAt)}
        </p>
      </div>

      <section>
        <h3 className="mb-1.5 text-[10px] font-semibold tracking-[0.08em] text-text-faint uppercase">
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

      <section>
        <h3 className="mb-2 text-[10px] font-semibold tracking-[0.08em] text-text-faint uppercase">
          Progress
        </h3>
        <ProgressTracker ticket={ticket} events={events} />
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
