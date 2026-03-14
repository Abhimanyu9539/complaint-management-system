import type { ReactNode } from 'react';
import { StatusPill } from '@/components/ui/StatusPill';
import { formatTimestamp } from '@/lib/format';
import { resolutionPathTone, severityLabel, severityTone } from '@/lib/status';
import type { TicketDetail } from '@/lib/tickets/types';
import { TicketTimeline } from './TicketTimeline';

/**
 * A ticket's read-only detail: subject, severity/source/routing, the complaint
 * body, and its full event history.
 *
 * Shared by the admin drawer and the workbench's complaint pane so the two
 * cannot render a ticket's own facts differently.
 */
export function TicketBody({ detail }: { detail: TicketDetail }) {
  const { ticket, events } = detail;

  return (
    <div className="flex flex-col gap-5">
      <div>
        <h3 className="text-[14px] leading-snug font-semibold text-text">{ticket.subject}</h3>
        <p className="mt-1 text-[11.5px] text-text-faint">
          {ticket.customerEmail ?? 'No reply address'} · opened {formatTimestamp(ticket.createdAt)}
        </p>
      </div>

      <dl className="grid grid-cols-2 gap-x-4 gap-y-2.5 text-[11.5px]">
        <Detail label="Severity">
          <StatusPill label={severityLabel(ticket.severity)} tone={severityTone(ticket.severity)} />
        </Detail>
        <Detail label="Source">
          <span className="text-text capitalize">{ticket.source}</span>
        </Detail>
        <Detail label="Escalated to">
          <span className="text-text">{ticket.escalatedDept ?? '—'}</span>
        </Detail>
        <Detail label="Resolution path">
          {ticket.resolutionPath ? (
            <StatusPill
              label={ticket.resolutionPath}
              tone={resolutionPathTone(ticket.resolutionPath)}
            />
          ) : (
            // Not "direct". A ticket that has not resolved has no path, and
            // defaulting it would silently classify it as a first-line win.
            <span className="text-text-faint">Not yet resolved</span>
          )}
        </Detail>
      </dl>

      <section>
        <h4 className="mb-1.5 text-[10px] font-semibold tracking-[0.08em] text-text-faint uppercase">
          Complaint
        </h4>
        {ticket.body ? (
          <p className="rounded-lg border border-border bg-bg-elevated px-3 py-2.5 text-[12.5px] leading-relaxed whitespace-pre-wrap text-text">
            {ticket.body}
          </p>
        ) : (
          <p className="text-[12px] text-text-faint">
            No body recorded. Tickets created before the web intake landed carry a subject only.
          </p>
        )}
      </section>

      <section>
        <h4 className="mb-1.5 text-[10px] font-semibold tracking-[0.08em] text-text-faint uppercase">
          History
        </h4>
        <TicketTimeline events={events} />
      </section>
    </div>
  );
}

function Detail({ label, children }: { label: string; children: ReactNode }) {
  return (
    <div className="flex min-w-0 flex-col gap-1">
      <dt className="text-[10px] font-semibold tracking-[0.08em] text-text-faint uppercase">
        {label}
      </dt>
      <dd className="min-w-0 truncate">{children}</dd>
    </div>
  );
}
