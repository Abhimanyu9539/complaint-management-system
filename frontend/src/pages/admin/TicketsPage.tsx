import { useCallback, useMemo, useState } from 'react';
import { AdminPageHeader } from '@/components/admin/layout/AdminShell';
import { LiveIndicator } from '@/components/admin/layout/LiveIndicator';
import { TicketDrawer } from '@/components/admin/tickets/TicketDrawer';
import { TicketsTable } from '@/components/admin/tickets/TicketsTable';
import { MockBadge } from '@/components/ui/MockBadge';
import { Pagination } from '@/components/ui/Pagination';
import { Panel } from '@/components/ui/Panel';
import { SearchInput } from '@/components/ui/SearchInput';
import { Select } from '@/components/ui/Select';
import { StatCard } from '@/components/ui/StatCard';
import { useAdminLayout } from '@/hooks/useAdminLayout';
import { usePanelData } from '@/hooks/usePanelData';
import { useQueryParamNumber, useQueryParamState } from '@/hooks/useQueryParamState';
import { formatCount, formatPercent } from '@/lib/format';
import { adminTransport } from '@/lib/admin/transport';
import { AdminRequestError } from '@/lib/admin/errors';
import type { TicketDetail, TicketSeverity, TicketStatus } from '@/lib/tickets/types';

const PAGE_SIZE = 25;

const STATUS_OPTIONS = [
  { value: 'all', label: 'All statuses' },
  { value: 'new', label: 'New' },
  { value: 'needs_review', label: 'Needs review' },
  { value: 'escalated', label: 'Escalated' },
  { value: 'dept_responded', label: 'Dept replied' },
  { value: 'resolved', label: 'Resolved' },
];

const SEVERITY_OPTIONS = [
  { value: 'all', label: 'All severities' },
  { value: 'critical', label: 'Critical' },
  { value: 'high', label: 'High' },
  { value: 'normal', label: 'Normal' },
  { value: 'low', label: 'Low' },
];

/**
 * The ticket queue.
 *
 * The three cards at the top are the escalation metric in miniature — the same
 * numbers the statistics page charts, put in front of the person who can move
 * them. `formatPercent` renders a null rate as an em dash rather than 0%, which
 * is the whole reason the backend returns null.
 */
export function TicketsPage() {
  const { openMobileNav } = useAdminLayout();

  const [status, setStatus] = useQueryParamState('status', 'all');
  const [severity, setSeverity] = useQueryParamState('severity', 'all');
  const [search, setSearch] = useQueryParamState('q', '');
  const [page, setPage] = useQueryParamNumber('page', 1);

  const [detail, setDetail] = useState<TicketDetail | null>(null);
  const [detailLoading, setDetailLoading] = useState(false);
  const [acting, setActing] = useState(false);
  const [actionError, setActionError] = useState<string | null>(null);

  const offset = (page - 1) * PAGE_SIZE;
  const isFiltered = status !== 'all' || severity !== 'all' || search !== '';

  const tickets = usePanelData(
    'tickets',
    (signal) =>
      adminTransport.listTickets(
        {
          status: status as TicketStatus | 'all',
          severity: severity as TicketSeverity | 'all',
          search,
          limit: PAGE_SIZE,
          offset,
        },
        signal,
      ),
    { deps: [status, severity, search, offset] },
  );

  const escalation = usePanelData('tickets-escalation', (signal) =>
    adminTransport.getEscalationSummary(30, signal),
  );

  // Fetched once for the escalate picker rather than per drawer open: the set
  // is closed at twelve and changes only with a migration.
  const departments = usePanelData(
    'departments',
    (signal) => adminTransport.listDepartments(signal),
    { intervalFactor: 30 },
  );

  const departmentLabel = useCallback(
    (id: string | null) => {
      if (!id) return 'Unrouted';
      return departments.data?.find((entry) => entry.id === id)?.name ?? id;
    },
    [departments.data],
  );

  const openTicket = useCallback(async (ticketId: string) => {
    setActionError(null);
    setDetailLoading(true);
    const controller = new AbortController();
    try {
      const result = await adminTransport.getTicket(ticketId, controller.signal);
      setDetail(result.data);
    } catch (err) {
      console.warn('tickets: failed to load ticket detail', err);
      setDetail(null);
      setActionError(
        err instanceof AdminRequestError ? err.message : 'Could not load that ticket.',
      );
    } finally {
      setDetailLoading(false);
    }
  }, []);

  /**
   * Escalate and resolve share everything except the call, so they share a
   * runner. The refreshes matter: an action changes the row, the queue counts
   * and the escalation rate at once, and refreshing only the drawer would leave
   * a resolved ticket sitting in the list behind it.
   */
  const runAction = useCallback(
    async (action: (signal: AbortSignal) => Promise<unknown>, ticketId: string) => {
      setActing(true);
      setActionError(null);
      const controller = new AbortController();
      try {
        await action(controller.signal);
        await openTicket(ticketId);
        tickets.refresh();
        escalation.refresh();
      } catch (err) {
        setActionError(
          err instanceof AdminRequestError
            ? err.message
            : 'That action failed. Please try again.',
        );
      } finally {
        setActing(false);
      }
    },
    [openTicket, tickets, escalation],
  );

  const handleEscalate = useCallback(
    async (departmentId: string, note: string) => {
      const ticketId = detail?.ticket.id;
      if (!ticketId) return;
      await runAction(
        (signal) =>
          adminTransport.escalateTicket(ticketId, departmentId, note.trim() || null, signal),
        ticketId,
      );
    },
    [detail, runAction],
  );

  const handleResolve = useCallback(
    async (note: string) => {
      const ticketId = detail?.ticket.id;
      if (!ticketId) return;
      await runAction(
        (signal) => adminTransport.resolveTicket(ticketId, note.trim() || null, signal),
        ticketId,
      );
    },
    [detail, runAction],
  );

  const summary = escalation.data;
  const openCount = useMemo(() => {
    if (!summary) return 0;
    // Everything that is not a terminal state. Derived from the funnel rather
    // than a separate count so the two can never disagree.
    const resolved = summary.byStatus.resolved ?? 0;
    return summary.totalTickets - resolved;
  }, [summary]);

  return (
    <>
      <AdminPageHeader
        title="Tickets"
        description="Customer complaints, and the path each one took"
        onOpenNav={openMobileNav}
        actions={<LiveIndicator />}
      />

      <div className="flex flex-col gap-4 p-4">
        <div className="grid grid-cols-1 gap-4 sm:grid-cols-3">
          <StatCard
            label="Open tickets"
            value={formatCount(openCount)}
            hint={`${formatCount(summary?.totalTickets)} total`}
            status={escalation.status}
            mocked={escalation.mocked}
            mockReason={escalation.note ?? undefined}
          />
          <StatCard
            label="Awaiting a department"
            value={formatCount(summary?.openEscalated)}
            hint="escalated, no reply yet"
            tone={(summary?.openEscalated ?? 0) > 0 ? 'warn' : 'neutral'}
            status={escalation.status}
            mocked={escalation.mocked}
            mockReason={escalation.note ?? undefined}
          />
          <StatCard
            label="Escalation rate"
            value={formatPercent(summary?.escalationRate, 1)}
            hint={
              summary?.escalationRate === null || summary?.escalationRate === undefined
                ? 'no resolved tickets yet'
                : `${formatCount(summary.resolvedEscalated)} of ${formatCount(
                    summary.resolvedDirect + summary.resolvedEscalated,
                  )} resolved`
            }
            status={escalation.status}
            mocked={escalation.mocked}
            mockReason={escalation.note ?? undefined}
          />
        </div>

        <Panel
          title="Complaint queue"
          eyebrow="Tickets"
          flush
          actions={tickets.mocked && tickets.note ? <MockBadge reason={tickets.note} /> : undefined}
        >
          <div className="flex flex-wrap items-end gap-2 px-4 pb-3">
            <Select label="Status" value={status} onChange={setStatus} options={STATUS_OPTIONS} />
            <Select
              label="Severity"
              value={severity}
              onChange={setSeverity}
              options={SEVERITY_OPTIONS}
            />
            <SearchInput
              value={search}
              onChange={setSearch}
              placeholder="Search subject or email…"
              className="min-w-[200px] flex-1"
            />
          </div>

          <TicketsTable
            tickets={tickets}
            onSelect={(ticket) => void openTicket(ticket.id)}
            activeTicketId={detail?.ticket.id ?? null}
            emptyIsFiltered={isFiltered}
            departmentLabel={departmentLabel}
          />

          <Pagination
            total={tickets.data?.total ?? 0}
            limit={PAGE_SIZE}
            offset={offset}
            onChange={(nextOffset) => setPage(Math.floor(nextOffset / PAGE_SIZE) + 1)}
            className="border-t border-border"
          />
        </Panel>
      </div>

      <TicketDrawer
        detail={detail}
        loading={detailLoading}
        departments={departments.data ?? []}
        onClose={() => {
          setDetail(null);
          setActionError(null);
        }}
        onEscalate={handleEscalate}
        onResolve={handleResolve}
        actionError={actionError}
        acting={acting}
      />
    </>
  );
}
