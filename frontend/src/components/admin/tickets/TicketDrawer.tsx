import { CircleCheck, Send, TriangleAlert } from 'lucide-react';
import { useState } from 'react';
import { Button } from '@/components/ui/Button';
import { Drawer } from '@/components/ui/Drawer';
import { Select } from '@/components/ui/Select';
import { StatusPill } from '@/components/ui/StatusPill';
import { TextArea } from '@/components/ui/TextArea';
import { formatTimestamp } from '@/lib/format';
import {
  resolutionPathTone,
  severityLabel,
  severityTone,
  ticketStatusLabel,
  ticketStatusTone,
} from '@/lib/status';
import type { DepartmentOption } from '@/lib/admin/types';
import type { Ticket, TicketDetail, TicketStatus } from '@/lib/tickets/types';

/**
 * The two edges of `ticket_service.ALLOWED` this UI can drive.
 *
 * Mirrored from the backend so the buttons disable instead of offering an
 * action that will come back 409. The backend is still the authority — this is
 * the difference between a refusal the operator saw coming and one that looks
 * like a bug.
 */
const CAN_ESCALATE = new Set<TicketStatus>(['new', 'drafted', 'needs_review', 'dept_responded']);
const CAN_RESOLVE = new Set<TicketStatus>([
  'new',
  'drafted',
  'needs_review',
  'escalated',
  'dept_responded',
]);

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

function TicketBody({ detail }: { detail: TicketDetail }) {
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
      </section>
    </div>
  );
}

function Detail({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <div className="flex min-w-0 flex-col gap-1">
      <dt className="text-[10px] font-semibold tracking-[0.08em] text-text-faint uppercase">
        {label}
      </dt>
      <dd className="min-w-0 truncate">{children}</dd>
    </div>
  );
}

/**
 * Escalate and resolve.
 *
 * Escalation opens a department picker rather than firing immediately — cms.md
 * §4.3 wants the prediction pre-selected and every override recorded, because
 * an override is a training label. There is no classifier yet, so the picker
 * starts on the prediction when there is one and on nothing when there is not,
 * which is the honest version of the same interaction.
 */
function TicketActions({
  ticket,
  departments,
  onEscalate,
  onResolve,
  error,
  acting,
}: {
  ticket: Ticket;
  departments: DepartmentOption[];
  onEscalate(departmentId: string, note: string): Promise<void>;
  onResolve(note: string): Promise<void>;
  error: string | null;
  acting: boolean;
}) {
  const [mode, setMode] = useState<'idle' | 'escalate' | 'resolve'>('idle');
  const [department, setDepartment] = useState(ticket.predictedDept ?? '');
  const [note, setNote] = useState('');

  const canEscalate = CAN_ESCALATE.has(ticket.status);
  const canResolve = CAN_RESOLVE.has(ticket.status);

  if (!canEscalate && !canResolve) {
    return (
      <p className="text-[11.5px] text-text-faint">
        {ticket.status === 'resolved'
          ? 'This ticket is closed. Reopening happens when a customer replies again.'
          : 'No actions are available from this state.'}
      </p>
    );
  }

  return (
    <div className="flex flex-col gap-3">
      {error && (
        <p
          role="alert"
          className="flex items-start gap-1.5 rounded-lg border border-danger/30 bg-danger-soft px-2.5 py-2 text-[11.5px] leading-relaxed text-danger"
        >
          <TriangleAlert size={13} strokeWidth={2} className="mt-px shrink-0" />
          {error}
        </p>
      )}

      {mode === 'escalate' && (
        <div className="flex flex-col gap-2.5">
          <Select
            label="Department"
            size="md"
            value={department}
            onChange={setDepartment}
            options={[
              { value: '', label: 'Select a department…' },
              ...departments.map((entry) => ({ value: entry.id, label: entry.name })),
            ]}
          />
          <TextArea
            label="Question for the department"
            value={note}
            onChange={setNote}
            rows={3}
            maxLength={2000}
            hint="Recorded on the audit log. Optional."
          />
        </div>
      )}

      {mode === 'resolve' && (
        <TextArea
          label="Resolution note"
          value={note}
          onChange={setNote}
          rows={3}
          maxLength={2000}
          hint={
            ticket.escalatedDept
              ? 'This ticket was escalated, so it will be recorded as Path B.'
              : 'No department was involved, so it will be recorded as Path A (direct).'
          }
        />
      )}

      <div className="flex items-center justify-end gap-2">
        {mode !== 'idle' && (
          <Button
            variant="ghost"
            onClick={() => {
              setMode('idle');
              setNote('');
            }}
            disabled={acting}
          >
            Cancel
          </Button>
        )}

        {mode === 'idle' && canEscalate && (
          <Button
            variant="secondary"
            icon={<Send size={13} strokeWidth={2} />}
            onClick={() => setMode('escalate')}
          >
            Escalate
          </Button>
        )}
        {mode === 'idle' && canResolve && (
          <Button
            variant="primary"
            icon={<CircleCheck size={13} strokeWidth={2} />}
            onClick={() => setMode('resolve')}
          >
            Resolve
          </Button>
        )}

        {mode === 'escalate' && (
          <Button
            variant="primary"
            loading={acting}
            disabled={acting || !department}
            onClick={() => void onEscalate(department, note)}
          >
            Send to department
          </Button>
        )}
        {mode === 'resolve' && (
          <Button
            variant="primary"
            loading={acting}
            disabled={acting}
            onClick={() => void onResolve(note)}
          >
            Mark resolved
          </Button>
        )}
      </div>
    </div>
  );
}
