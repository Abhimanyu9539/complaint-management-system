import { Inbox } from 'lucide-react';
import { useCallback, useEffect, useMemo } from 'react';
import { ComplaintPane } from '@/components/workbench/ComplaintPane';
import { DraftPane } from '@/components/workbench/DraftPane';
import { EvidencePane } from '@/components/workbench/EvidencePane';
import { WorkbenchShell } from '@/components/workbench/WorkbenchShell';
import { EmptyState } from '@/components/ui/EmptyState';
import { useAsyncData } from '@/hooks/useAsyncData';
import { useQueryParamState } from '@/hooks/useQueryParamState';
import { useTicketActions } from '@/hooks/useTicketActions';
import { adminTransport } from '@/lib/admin/transport';
import { flattenQueueOrder } from '@/lib/tickets/queue';
import type { TicketSeverity, TicketStatus } from '@/lib/tickets/types';

/** The backend's per-request ceiling (`limit`, `le=100`) — see `QueueRail`'s docstring. */
const QUEUE_LIMIT = 100;

/**
 * The complaint workbench — the app's main page.
 *
 * Triages one ticket at a time: a queue organised by status on the left
 * (`QueueRail`), and three panes on the right — the complaint and its real
 * progress (`ComplaintPane`), the drafted reply (`DraftPane`), and the evidence
 * it cites (`EvidencePane`). Sending the reply emails the customer and resolves
 * the ticket; escalate/resolve are the ticket-level actions.
 *
 * Deliberately does not mount `ChatProvider` — same rule as `/ticket`, stated
 * once in `App.tsx`.
 */
export function WorkbenchPage() {
  const [statusFilter, setStatusFilter] = useQueryParamState('status', 'all');
  const [search, setSearch] = useQueryParamState('q', '');
  const [ticketId, setTicketId] = useQueryParamState('ticket', '');

  const queue = useAsyncData(
    (signal) =>
      adminTransport.listTickets(
        {
          status: statusFilter as TicketStatus | 'all',
          severity: 'all' as TicketSeverity | 'all',
          search,
          limit: QUEUE_LIMIT,
          offset: 0,
        },
        signal,
      ),
    { intervalMs: 20_000, deps: [statusFilter, search] },
  );

  const departments = useAsyncData((signal) => adminTransport.listDepartments(signal), {
    intervalMs: 20_000 * 30,
  });
  const departmentLabel = useCallback(
    (id: string | null) => {
      if (!id) return 'Unrouted';
      return departments.data?.find((entry) => entry.id === id)?.name ?? id;
    },
    [departments.data],
  );

  const ticketActions = useTicketActions(() => queue.refresh());
  const {
    detail,
    detailLoading,
    acting,
    actionError,
    openTicket,
    escalate,
    resolve,
    sendReply,
    discard,
    regenerate,
    clear,
  } = ticketActions;

  // The selected ticket lives in the URL, so loading it is a side effect of
  // that value changing rather than of a click — a shared link, the back
  // button and `J`/`K` all drive the same path.
  useEffect(() => {
    if (ticketId) {
      void openTicket(ticketId);
    } else {
      clear();
    }
    // `openTicket`/`clear` are stable (useCallback with empty deps in the hook).
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [ticketId]);

  // The latest escalation, for the Draft pane's banner. Events come oldest first.
  const escalation = useMemo(() => {
    const event = detail?.events.filter((entry) => entry.event === 'escalated').at(-1);
    if (!detail || !event) return null;
    const note = event.payload.note;
    return {
      department: departmentLabel(detail.ticket.escalatedDept),
      question: typeof note === 'string' && note.trim() ? note : null,
      at: event.createdAt,
    };
  }, [detail, departmentLabel]);

  // While the ticket graph runs, reload the ticket so its draft appears on its own.
  const processingId = detail?.ticket.status === 'processing' ? detail.ticket.id : null;
  useEffect(() => {
    if (!processingId) return;
    const timer = setInterval(() => void openTicket(processingId), 5_000);
    return () => clearInterval(timer);
  }, [processingId, openTicket]);

  const select = useCallback((id: string) => setTicketId(id), [setTicketId]);

  const flatOrder = useMemo(() => flattenQueueOrder(queue.data?.items ?? []), [queue.data]);

  // `J`/`K` queue navigation, ignoring keystrokes aimed at a form control.
  useEffect(() => {
    function onKeyDown(event: KeyboardEvent) {
      const target = event.target as HTMLElement | null;
      if (target?.closest('input, textarea, select, [contenteditable="true"]')) return;
      if (event.key !== 'j' && event.key !== 'k') return;
      if (flatOrder.length === 0) return;

      const currentIndex = flatOrder.findIndex((ticket) => ticket.id === ticketId);
      const nextIndex =
        event.key === 'j'
          ? Math.min(currentIndex + 1, flatOrder.length - 1)
          : Math.max(currentIndex - 1, 0);
      const next = flatOrder[Math.max(nextIndex, 0)];
      if (next) select(next.id);
    }
    document.addEventListener('keydown', onKeyDown);
    return () => document.removeEventListener('keydown', onKeyDown);
  }, [flatOrder, ticketId, select]);

  return (
    <WorkbenchShell
      queue={queue}
      statusFilter={statusFilter}
      onStatusFilterChange={setStatusFilter}
      search={search}
      onSearchChange={setSearch}
      selectedId={ticketId || null}
      onSelect={select}
      departmentLabel={departmentLabel}
    >
      {!ticketId ? (
        <div className="flex h-full items-center justify-center">
          <EmptyState
            icon={<Inbox size={22} strokeWidth={1.5} />}
            title="Select a ticket"
            description="Pick a complaint from the queue — or press J to jump to the first one."
          />
        </div>
      ) : (
        <div className="scrollbar-thin grid min-h-0 flex-1 grid-cols-1 overflow-y-auto lg:grid-cols-[minmax(280px,1fr)_minmax(320px,1.25fr)_320px] lg:overflow-hidden">
          <div className="lg:min-h-0 lg:overflow-y-auto lg:border-r lg:border-border">
            <ComplaintPane detail={detail} loading={detailLoading} />
          </div>
          <div className="border-t border-border lg:min-h-0 lg:overflow-y-auto lg:border-t-0 lg:border-r lg:border-border">
            {detail && (
              <DraftPane
                ticket={detail.ticket}
                draft={detail.draft}
                escalation={escalation}
                onRefresh={() => void openTicket(detail.ticket.id)}
                onSend={sendReply}
                onDiscard={discard}
                onRegenerate={regenerate}
                departments={departments.data ?? []}
                onEscalate={escalate}
                onResolve={resolve}
                actionError={actionError}
                acting={acting}
              />
            )}
          </div>
          <div className="border-t border-border lg:min-h-0 lg:overflow-y-auto lg:border-t-0">
            {detail && (
              <EvidencePane
                ticket={detail.ticket}
                // While a new draft is being written, the old one's evidence is stale.
                draft={detail.ticket.status === 'processing' ? null : detail.draft}
                departmentLabel={departmentLabel}
              />
            )}
          </div>
        </div>
      )}
    </WorkbenchShell>
  );
}
