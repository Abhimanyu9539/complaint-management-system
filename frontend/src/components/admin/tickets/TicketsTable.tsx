import { Inbox, SquareArrowOutUpRight } from 'lucide-react';
import { Link } from 'react-router';
import { DataTable, type Column } from '@/components/ui/DataTable';
import { EmptyState } from '@/components/ui/EmptyState';
import { StatusPill } from '@/components/ui/StatusPill';
import { formatRelativeTime } from '@/lib/format';
import { severityLabel, severityTone, ticketStatusLabel, ticketStatusTone } from '@/lib/status';
import type { AsyncData } from '@/hooks/useAsyncData';
import type { Page } from '@/lib/admin/types';
import type { Ticket } from '@/lib/tickets/types';

interface TicketsTableProps {
  tickets: AsyncData<Page<Ticket>>;
  onSelect(ticket: Ticket): void;
  activeTicketId?: string | null;
  /** Changes the empty copy: "nothing matched" is not "nothing exists". */
  emptyIsFiltered?: boolean;
  departmentLabel(id: string | null): string;
}

export function TicketsTable({
  tickets,
  onSelect,
  activeTicketId = null,
  emptyIsFiltered = false,
  departmentLabel,
}: TicketsTableProps) {
  const columns: Column<Ticket>[] = [
    {
      key: 'ref',
      header: 'Ref',
      width: 'w-[104px]',
      render: (ticket) => (
        <span className="flex items-center gap-1.5">
          <span className="font-mono text-[11.5px] text-text-muted tabular-nums">
            T-{ticket.ticketNo}
          </span>
          <Link
            to={`/?ticket=${ticket.id}`}
            title="Open in workbench"
            aria-label={`Open T-${ticket.ticketNo} in the workbench`}
            onClick={(event) => event.stopPropagation()}
            className="text-text-faint transition-colors hover:text-accent"
          >
            <SquareArrowOutUpRight size={12} strokeWidth={1.75} />
          </Link>
        </span>
      ),
    },
    {
      key: 'status',
      header: 'Status',
      width: 'w-[124px]',
      render: (ticket) => (
        <StatusPill
          label={ticketStatusLabel(ticket.status)}
          tone={ticketStatusTone(ticket.status)}
        />
      ),
    },
    {
      key: 'subject',
      header: 'Subject',
      render: (ticket) => (
        <div className="min-w-0">
          <p className="truncate text-text">{ticket.subject}</p>
          <p className="truncate text-[11px] text-text-faint">
            {ticket.customerEmail ?? 'No reply address'}
          </p>
        </div>
      ),
    },
    {
      key: 'severity',
      header: 'Severity',
      width: 'w-[100px]',
      secondary: true,
      render: (ticket) => (
        <StatusPill label={severityLabel(ticket.severity)} tone={severityTone(ticket.severity)} />
      ),
    },
    {
      key: 'department',
      header: 'Department',
      width: 'w-[150px]',
      secondary: true,
      render: (ticket) => {
        // The escalated department is the fact; the predicted one is a guess.
        // Showing them identically would make a routing prediction look like a
        // decision somebody made.
        if (ticket.escalatedDept) {
          return <span className="truncate text-text">{departmentLabel(ticket.escalatedDept)}</span>;
        }
        if (ticket.predictedDept) {
          return (
            <span className="truncate text-text-faint italic">
              {departmentLabel(ticket.predictedDept)}?
            </span>
          );
        }
        return <span className="text-text-faint">—</span>;
      },
    },
    {
      key: 'age',
      header: 'Opened',
      width: 'w-[104px]',
      numeric: true,
      render: (ticket) => (
        <span className="text-text-muted">{formatRelativeTime(ticket.createdAt)}</span>
      ),
    },
  ];

  return (
    <DataTable
      caption="Customer complaint tickets"
      columns={columns}
      rows={tickets.data?.items ?? []}
      rowKey={(ticket) => ticket.id}
      status={tickets.status}
      error={tickets.error}
      errorDetail={tickets.errorDetail}
      failureCount={tickets.failureCount}
      onRetry={tickets.refresh}
      // An inline arrow rather than passing `onSelect` directly: handing a
      // setState function straight in makes DataTable's generic infer the
      // SetStateAction union instead of Ticket.
      onRowClick={(ticket) => onSelect(ticket)}
      activeRowKey={activeTicketId}
      empty={
        emptyIsFiltered ? (
          <EmptyState
            icon={<Inbox size={18} strokeWidth={1.5} />}
            title="No tickets match these filters"
            description="Clear or widen the filters to see the rest of the queue."
          />
        ) : (
          <EmptyState
            icon={<Inbox size={18} strokeWidth={1.5} />}
            title="No complaints yet"
            description="Tickets appear here as customers submit them through the /ticket form."
          />
        )
      }
    />
  );
}
