import { CircleCheck, Send, TriangleAlert } from 'lucide-react';
import { useState } from 'react';
import { Button } from '@/components/ui/Button';
import { Select } from '@/components/ui/Select';
import { TextArea } from '@/components/ui/TextArea';
import { canEscalate, canResolve } from '@/lib/tickets/transitions';
import type { DepartmentOption } from '@/lib/admin/types';
import type { Ticket } from '@/lib/tickets/types';

/**
 * Escalate and resolve.
 *
 * Escalation opens a department picker rather than firing immediately — cms.md
 * §4.3 wants the prediction pre-selected and every override recorded, because
 * an override is a training label. There is no classifier yet, so the picker
 * starts on the prediction when there is one and on nothing when there is not,
 * which is the honest version of the same interaction.
 *
 * Shared by `/admin/tickets` and the workbench — one form, driven by
 * `lib/tickets/transitions`, so the two surfaces cannot offer an action the
 * backend's state machine will refuse.
 */
export function TicketActions({
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

  const escalateAllowed = canEscalate(ticket.status);
  const resolveAllowed = canResolve(ticket.status);

  if (!escalateAllowed && !resolveAllowed) {
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

        {mode === 'idle' && escalateAllowed && (
          <Button
            variant="secondary"
            icon={<Send size={13} strokeWidth={2} />}
            onClick={() => setMode('escalate')}
          >
            Escalate
          </Button>
        )}
        {mode === 'idle' && resolveAllowed && (
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
