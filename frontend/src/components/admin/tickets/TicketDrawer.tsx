import { Drawer } from '@/components/ui/Drawer';
import { StatusPill } from '@/components/ui/StatusPill';
import { TicketActions } from '@/components/tickets/TicketActions';
import { TicketBody } from '@/components/tickets/TicketBody';
import { ticketStatusLabel, ticketStatusTone } from '@/lib/status';
import type { DepartmentOption } from '@/lib/admin/types';
import type { TicketDetail } from '@/lib/tickets/types';

interface TicketDrawerProps {
  detail: TicketDetail | null;
  loading: boolean;
  departments: DepartmentOption[];
  onClose(): void;
  onEscalate(departmentId: string, note: string): Promise<void>;
  onResolve(note: string): Promise<void>;
  /** Set when the last action was refused, e.g. by the state machine. */
  actionError: string | null;
  acting: boolean;
}

/**
 * The admin queue's row-detail drawer.
 *
 * A thin shell around `TicketBody`/`TicketActions` (`components/tickets/`),
 * which the workbench at `/` also renders — inline rather than in a drawer,
 * since a modal overlay is wrong for a permanent third pane.
 */
export function TicketDrawer({
  detail,
  loading,
  departments,
  onClose,
  onEscalate,
  onResolve,
  actionError,
  acting,
}: TicketDrawerProps) {
  const ticket = detail?.ticket ?? null;

  return (
    <Drawer
      open={Boolean(detail) || loading}
      onClose={onClose}
      title={ticket ? `T-${ticket.ticketNo}` : 'Ticket'}
      actions={
        ticket && (
          <StatusPill
            label={ticketStatusLabel(ticket.status)}
            tone={ticketStatusTone(ticket.status)}
          />
        )
      }
      footer={
        ticket && (
          <TicketActions
            ticket={ticket}
            departments={departments}
            onEscalate={onEscalate}
            onResolve={onResolve}
            error={actionError}
            acting={acting}
          />
        )
      }
    >
      {!detail ? (
        <p className="text-[12px] text-text-faint">Loading…</p>
      ) : (
        <TicketBody detail={detail} />
      )}
    </Drawer>
  );
}
