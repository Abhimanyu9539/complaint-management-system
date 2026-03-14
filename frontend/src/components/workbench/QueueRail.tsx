import { Inbox } from 'lucide-react';
import { SidebarFooter } from '@/components/layout/SidebarFooter';
import { AsyncBoundary } from '@/components/ui/AsyncBoundary';
import { EmptyState } from '@/components/ui/EmptyState';
import { MockBadge } from '@/components/ui/MockBadge';
import { SearchInput } from '@/components/ui/SearchInput';
import { Select } from '@/components/ui/Select';
import { Skeleton } from '@/components/ui/Skeleton';
import { useMockAdmin } from '@/lib/admin/transport';
import { ticketStatusLabel } from '@/lib/status';
import { QUEUE_GROUP_ORDER, groupTicketsByStatus } from '@/lib/tickets/queue';
import type { AsyncData } from '@/hooks/useAsyncData';
import type { Page } from '@/lib/admin/types';
import type { Ticket } from '@/lib/tickets/types';
import { QueueRow } from './QueueRow';

const STATUS_FILTER_OPTIONS = [
  { value: 'all', label: 'All statuses' },
  ...QUEUE_GROUP_ORDER.map((status) => ({ value: status, label: ticketStatusLabel(status) })),
];

interface QueueRailProps {
  queue: AsyncData<Page<Ticket>>;
  statusFilter: string;
  onStatusFilterChange(value: string): void;
  search: string;
  onSearchChange(value: string): void;
  selectedId: string | null;
  onSelect(id: string): void;
  departmentLabel(id: string | null): string;
  /** Closes the mobile drawer this rail is rendered inside, if any. */
  onCloseMobile?(): void;
}

/**
 * The complaint queue, organised by status — the user's own words for what the
 * main page should show.
 *
 * "All statuses" groups every ticket under its status heading, zero-count
 * groups included (see `lib/tickets/queue`). Filtering to one status collapses
 * to a flat list — the heading would just repeat the filter back.
 *
 * Fetches the most recent 100 tickets (the backend's per-request ceiling) and
 * groups them client-side. `/admin/tickets` remains the place for searching or
 * paging past that — this rail is for triage, not for finding one ticket in a
 * large archive.
 */
export function QueueRail({
  queue,
  statusFilter,
  onStatusFilterChange,
  search,
  onSearchChange,
  selectedId,
  onSelect,
  departmentLabel,
  onCloseMobile,
}: QueueRailProps) {
  const items = queue.data?.items ?? [];
  const total = queue.data?.total ?? 0;
  const open = items.filter((ticket) => ticket.status !== 'resolved').length;
  const filtered = statusFilter !== 'all' || search !== '';

  const handleSelect = (id: string) => {
    onSelect(id);
    onCloseMobile?.();
  };

  return (
    <div className="flex h-full flex-col bg-surface">
      <div className="flex items-baseline justify-between gap-2 px-3.5 pt-3.5 pb-2">
        <h1 className="text-[12px] font-semibold tracking-[0.05em] text-text uppercase">Queue</h1>
        <span className="text-[11px] text-text-faint tabular-nums">
          {open} open · {total} total
          {total > items.length ? ` (showing ${items.length})` : ''}
        </span>
      </div>

      <div className="flex flex-col gap-2 px-3 pb-2.5">
        <Select
          label="Status"
          hideLabel
          value={statusFilter}
          onChange={onStatusFilterChange}
          options={STATUS_FILTER_OPTIONS}
        />
        <SearchInput value={search} onChange={onSearchChange} placeholder="Search subject or email…" />
      </div>

      {queue.mocked && queue.note && (
        <div className="px-3 pb-2.5">
          <MockBadge reason={queue.note} variant="banner" />
        </div>
      )}

      <div className="scrollbar-thin min-h-0 flex-1 overflow-y-auto px-2 pb-3">
        <AsyncBoundary
          status={queue.status}
          error={queue.error}
          errorDetail={queue.errorDetail}
          failureCount={queue.failureCount}
          onRetry={queue.refresh}
          isEmpty={items.length === 0}
          skeleton={
            <div className="flex flex-col gap-1.5 px-0.5 pt-1">
              {Array.from({ length: 6 }, (_, index) => (
                <Skeleton key={index} className="h-11 w-full rounded-lg" />
              ))}
            </div>
          }
          empty={
            <EmptyState
              icon={<Inbox size={18} strokeWidth={1.5} />}
              title={filtered ? 'No tickets match these filters' : 'No complaints yet'}
              description={
                filtered
                  ? 'Clear or widen the filters to see the rest of the queue.'
                  : 'Tickets appear here as customers submit them through the /ticket form.'
              }
            />
          }
        >
          {statusFilter === 'all' ? (
            <div className="flex flex-col gap-3">
              {groupTicketsByStatus(items).map((group) => (
                <section key={group.status}>
                  <div className="flex items-center justify-between px-1.5 pb-1">
                    <h2 className="text-[10.5px] font-semibold tracking-[0.06em] text-text-faint uppercase">
                      {ticketStatusLabel(group.status)}
                    </h2>
                    <span className="text-[10.5px] text-text-faint tabular-nums">
                      {group.tickets.length}
                    </span>
                  </div>
                  {group.tickets.length > 0 && (
                    <div className="flex flex-col gap-1">
                      {group.tickets.map((ticket) => (
                        <QueueRow
                          key={ticket.id}
                          ticket={ticket}
                          active={ticket.id === selectedId}
                          onSelect={() => handleSelect(ticket.id)}
                          departmentLabel={departmentLabel}
                        />
                      ))}
                    </div>
                  )}
                </section>
              ))}
            </div>
          ) : (
            <div className="flex flex-col gap-1">
              {items.map((ticket) => (
                <QueueRow
                  key={ticket.id}
                  ticket={ticket}
                  active={ticket.id === selectedId}
                  onSelect={() => handleSelect(ticket.id)}
                  departmentLabel={departmentLabel}
                />
              ))}
            </div>
          )}
        </AsyncBoundary>
      </div>

      <SidebarFooter
        mocked={useMockAdmin}
        mockedReason="No VITE_API_BASE_URL configured — the queue is showing simulated data."
        onNavigate={onCloseMobile}
      />
    </div>
  );
}
