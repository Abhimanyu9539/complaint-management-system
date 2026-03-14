import { formatTimestamp } from '@/lib/format';
import type { TicketEvent } from '@/lib/tickets/types';

/**
 * The append-only `ticket_events` audit trail, rendered as a vertical timeline.
 *
 * Shared by the admin drawer and the workbench's complaint pane — one
 * rendering of the audit log, since a timeline that looked different in two
 * places would read as two different histories.
 */
export function TicketTimeline({ events }: { events: TicketEvent[] }) {
  return (
    <ol className="flex flex-col gap-0">
      {events.map((event, index) => (
        <li key={event.id} className="flex gap-2.5">
          <div className="flex flex-col items-center">
            <span className="mt-1.5 h-1.5 w-1.5 shrink-0 rounded-full bg-accent" />
            {index < events.length - 1 && <span className="w-px flex-1 bg-border" />}
          </div>
          <div className="min-w-0 flex-1 pb-3">
            <p className="text-[12px] font-medium text-text">{event.event}</p>
            <p className="text-[11px] text-text-faint">
              {formatTimestamp(event.createdAt)}
              {event.actorId ? '' : ' · system'}
            </p>
            {typeof event.payload.note === 'string' && event.payload.note && (
              <p className="mt-1 text-[11.5px] leading-relaxed text-text-muted">
                {event.payload.note}
              </p>
            )}
          </div>
        </li>
      ))}
    </ol>
  );
}
