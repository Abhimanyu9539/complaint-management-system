import { Fragment, useState } from 'react';
import { AlertTriangle, CircleCheck, Clock, PencilLine, RefreshCw, Send, Trash2 } from 'lucide-react';
import { TicketActions } from '@/components/tickets/TicketActions';
import { Button } from '@/components/ui/Button';
import { Select } from '@/components/ui/Select';
import { TextArea } from '@/components/ui/TextArea';
import { formatTimestamp } from '@/lib/format';
import { canRegenerate, canSend, isDraftLocked } from '@/lib/tickets/transitions';
import type { DepartmentOption } from '@/lib/admin/types';
import type { DiscardReason, Ticket, TicketDraft } from '@/lib/tickets/types';

/** Where and when the ticket was escalated, from its latest `escalated` event. */
export interface EscalationInfo {
  department: string;
  question: string | null;
  at: string;
}

interface DraftPaneProps {
  ticket: Ticket;
  draft: TicketDraft | null;
  escalation: EscalationInfo | null;
  onRefresh(): void;
  onSend(draftId: string, finalText: string): Promise<void>;
  onDiscard(draftId: string, reason: DiscardReason, note: string): Promise<void>;
  onRegenerate(): Promise<void>;
  departments: DepartmentOption[];
  onEscalate(departmentId: string, note: string): Promise<void>;
  onResolve(note: string): Promise<void>;
  actionError: string | null;
  acting: boolean;
}

// `split` with a capture group keeps the markers: odd indices are the `[n]`s.
const MARKER_SPLIT = /(\[\d+\])/;

const DISCARD_REASONS: { value: DiscardReason; label: string }[] = [
  { value: 'wrong_case', label: 'Wrong precedent case' },
  { value: 'wrong_policy', label: 'Wrong policy' },
  { value: 'wrong_tone', label: 'Wrong tone' },
  { value: 'other', label: 'Other' },
];

function reasonLabel(reason: DiscardReason | null): string {
  return DISCARD_REASONS.find((entry) => entry.value === reason)?.label ?? 'no reason';
}

/** The text, with each `[n]` shown as a small superscript naming its source. */
function DraftText({ draft, text }: { draft: TicketDraft; text: string }) {
  const sources = new Map<number, string>([
    ...draft.policyRefs.map((ref) => [ref.marker, ref.section || ref.title] as const),
    ...draft.retrievedCases.map((item) => [item.marker, `Past case: ${item.title}`] as const),
  ]);

  return (
    <>
      {text.split(MARKER_SPLIT).map((part, index) => {
        if (index % 2 === 0) return <Fragment key={index}>{part}</Fragment>;
        const marker = Number(part.slice(1, -1));
        return (
          <sup
            key={index}
            title={sources.get(marker) ?? 'Unknown source'}
            className="ml-0.5 cursor-help font-mono text-[9.5px] text-accent"
          >
            {marker}
          </sup>
        );
      })}
    </>
  );
}

function Note({
  title,
  reasons = [],
  tone = 'warn',
}: {
  title: string;
  reasons?: string[];
  tone?: 'warn' | 'ok' | 'info';
}) {
  const colours = {
    ok: 'border-ok/30 bg-ok-soft text-ok',
    warn: 'border-warn/30 bg-warn-soft text-warn',
    info: 'border-accent/30 bg-accent-soft text-accent',
  }[tone];
  const Icon = { ok: CircleCheck, warn: AlertTriangle, info: Clock }[tone];
  return (
    <div className={`mb-2.5 flex items-start gap-2 rounded-lg border px-3 py-2 text-[12px] leading-relaxed ${colours}`}>
      <Icon size={14} strokeWidth={1.75} className="mt-0.5 shrink-0" />
      <div className="min-w-0">
        <p>{title}</p>
        {reasons.length > 0 && (
          <ul className="mt-1 list-disc pl-4">
            {reasons.map((reason) => (
              <li key={reason}>{reason}</li>
            ))}
          </ul>
        )}
      </div>
    </div>
  );
}

/**
 * One draft and what the agent can do with it. Keyed by draft id in the pane,
 * so a new version starts with fresh edit state.
 */
function DraftReply({
  ticket,
  draft,
  onSend,
  onDiscard,
  onRegenerate,
  acting,
}: Pick<DraftPaneProps, 'ticket' | 'onSend' | 'onDiscard' | 'onRegenerate' | 'acting'> & {
  draft: TicketDraft;
}) {
  const [text, setText] = useState(draft.draftText);
  const [editing, setEditing] = useState(false);
  const [mode, setMode] = useState<'idle' | 'confirm' | 'discard'>('idle');
  const [reason, setReason] = useState<DiscardReason>('wrong_case');
  const [note, setNote] = useState('');

  const edited = text.trim() !== draft.draftText.trim();
  const feedback = draft.feedback;

  if (feedback) {
    return (
      <>
        {feedback.action === 'rejected' ? (
          <Note title={`Discarded (${reasonLabel(feedback.editReason)}). Regenerate a new draft, or escalate.`} />
        ) : (
          <Note tone="ok" title={`Sent to the customer · ${feedback.action}.`} />
        )}
        <div className="rounded-lg border border-border bg-bg-elevated p-3.5 text-[12.5px] leading-relaxed whitespace-pre-wrap text-text-muted">
          {/* A sent draft shows exactly what the customer received; a discarded one, the draft. */}
          {feedback.finalText ?? <DraftText draft={draft} text={draft.draftText} />}
        </div>
        {feedback.action === 'rejected' && canRegenerate(ticket.status) && (
          <Button
            className="mt-2.5"
            icon={<RefreshCw size={13} strokeWidth={2} />}
            loading={acting}
            disabled={acting}
            onClick={() => void onRegenerate()}
          >
            Regenerate draft
          </Button>
        )}
      </>
    );
  }

  if (isDraftLocked(ticket.status)) {
    return (
      <>
        <div className="rounded-lg border border-border bg-bg-elevated p-3.5 text-[12.5px] leading-relaxed whitespace-pre-wrap text-text-muted">
          <DraftText draft={draft} text={draft.draftText} />
        </div>
        <p className="mt-1.5 text-[11px] text-text-faint">
          Version {draft.version} · read-only while the ticket is {ticket.status}
        </p>
      </>
    );
  }

  // An unedited holding reply only acknowledges the complaint; sending it would close the ticket.
  const sendBlocked = draft.noMatch && !edited;
  const sendAllowed = canSend(ticket.status) && Boolean(ticket.customerEmail) && !sendBlocked;

  return (
    <>
      {draft.noMatch && (
        <Note title="No policy matched this complaint. This is a holding reply that only acknowledges it — write the resolution into it, or escalate." />
      )}
      {draft.grounded === false && (
        <Note
          title="This draft failed the automated checks twice. Verify every claim against the evidence before using it:"
          reasons={draft.guardReasons}
        />
      )}

      {editing ? (
        <TextArea label="Reply" value={text} onChange={setText} rows={14} maxLength={8000} />
      ) : (
        <div className="rounded-lg border border-border bg-bg-elevated p-3.5 text-[12.5px] leading-relaxed whitespace-pre-wrap text-text">
          <DraftText draft={draft} text={text} />
        </div>
      )}
      <p className="mt-1.5 flex items-center gap-2 text-[11px] text-text-faint">
        Version {draft.version} · {draft.model} · prompt {draft.promptVersion}
        {edited && (
          <>
            <span className="rounded bg-accent-soft px-1.5 py-0.5 font-medium text-accent">Edited</span>
            <button type="button" className="underline" onClick={() => setText(draft.draftText)}>
              Reset
            </button>
          </>
        )}
      </p>

      {mode === 'confirm' && (
        <div className="mt-2.5 rounded-lg border border-border bg-surface p-3 text-[12px] text-text">
          Send this reply to <span className="font-medium">{ticket.customerEmail}</span>? The [n]
          markers are removed, and the ticket is resolved.
          <div className="mt-2.5 flex justify-end gap-2">
            <Button variant="ghost" onClick={() => setMode('idle')} disabled={acting}>
              Cancel
            </Button>
            <Button
              variant="primary"
              icon={<Send size={13} strokeWidth={2} />}
              loading={acting}
              disabled={acting}
              onClick={() => void onSend(draft.id, text)}
            >
              Send email
            </Button>
          </div>
        </div>
      )}

      {mode === 'discard' && (
        <div className="mt-2.5 flex flex-col gap-2.5 rounded-lg border border-border bg-surface p-3">
          <Select
            label="Why is this draft unusable?"
            size="md"
            value={reason}
            onChange={(value) => setReason(value as DiscardReason)}
            options={DISCARD_REASONS}
          />
          <TextArea label="Note" value={note} onChange={setNote} rows={2} maxLength={2000} hint="Optional." />
          <div className="flex justify-end gap-2">
            <Button variant="ghost" onClick={() => setMode('idle')} disabled={acting}>
              Cancel
            </Button>
            <Button
              variant="danger"
              loading={acting}
              disabled={acting}
              onClick={() => void onDiscard(draft.id, reason, note)}
            >
              Discard draft
            </Button>
          </div>
        </div>
      )}

      {mode === 'idle' && (
        <div className="mt-2.5 flex flex-wrap items-center gap-2">
          <Button
            icon={<PencilLine size={13} strokeWidth={2} />}
            onClick={() => setEditing((value) => !value)}
          >
            {editing ? 'Done editing' : 'Edit'}
          </Button>
          <Button
            variant="ghost"
            icon={<Trash2 size={13} strokeWidth={2} />}
            onClick={() => setMode('discard')}
          >
            Discard
          </Button>
          <span className="flex-1" />
          <Button
            variant="primary"
            icon={<Send size={13} strokeWidth={2} />}
            disabled={!sendAllowed}
            title={
              sendBlocked
                ? 'A holding reply only acknowledges the complaint. Edit it first, or escalate.'
                : !ticket.customerEmail
                  ? 'This ticket has no customer email address.'
                  : undefined
            }
            onClick={() => setMode('confirm')}
          >
            Send to customer
          </Button>
        </div>
      )}
    </>
  );
}

/**
 * The reply the ticket graph drafted for the customer. `[n]` markers stay in so
 * the operator can check each claim against the Evidence pane; sending removes
 * them. Escalate and Resolve below are the ticket-level actions.
 */
export function DraftPane({
  ticket,
  draft,
  escalation,
  onRefresh,
  onSend,
  onDiscard,
  onRegenerate,
  departments,
  onEscalate,
  onResolve,
  actionError,
  acting,
}: DraftPaneProps) {
  const regenerateButton = canRegenerate(ticket.status) && (
    <Button
      icon={<RefreshCw size={13} strokeWidth={2} />}
      loading={acting}
      disabled={acting}
      onClick={() => void onRegenerate()}
    >
      Regenerate draft
    </Button>
  );

  return (
    <div className="flex flex-col gap-4 p-4">
      <div>
        <h3 className="mb-2 text-[10px] font-semibold tracking-[0.08em] text-text-faint uppercase">
          Draft reply to customer
        </h3>

        {ticket.status === 'escalated' && (
          <Note
            tone="info"
            title={
              escalation
                ? `Escalated to ${escalation.department} · ${formatTimestamp(escalation.at)}. Waiting for the department's answer; the draft is locked until then.`
                : "Escalated. Waiting for the department's answer; the draft is locked until then."
            }
            reasons={escalation?.question ? [`Question: ${escalation.question}`] : []}
          />
        )}
        {ticket.status === 'needs_review' && ticket.reviewReasons.length > 0 && (
          <Note title="Needs review before sending:" reasons={ticket.reviewReasons} />
        )}
        {ticket.status === 'processing_failed' && (
          <Note title="Automatic drafting failed. The timeline shows why; regenerate to try again." />
        )}

        {ticket.status === 'processing' ? (
          <div className="rounded-lg border border-dashed border-border p-3.5 text-[12px] leading-relaxed text-text-muted">
            <p>Drafting in progress…</p>
            <Button className="mt-2" icon={<RefreshCw size={12} strokeWidth={2} />} onClick={onRefresh}>
              Check again
            </Button>
          </div>
        ) : draft ? (
          <DraftReply
            key={draft.id}
            ticket={ticket}
            draft={draft}
            onSend={onSend}
            onDiscard={onDiscard}
            onRegenerate={onRegenerate}
            acting={acting}
          />
        ) : (
          <div className="rounded-lg border border-dashed border-border p-3.5 text-[12px] leading-relaxed text-text-muted">
            <p>No draft yet. If drafting failed, the timeline shows why.</p>
            <div className="mt-2 flex gap-2">
              <Button icon={<RefreshCw size={12} strokeWidth={2} />} onClick={onRefresh}>
                Check again
              </Button>
              {regenerateButton}
            </div>
          </div>
        )}
        {ticket.status === 'processing_failed' && draft && <div className="mt-2.5">{regenerateButton}</div>}
      </div>

      <div className="border-t border-border pt-4">
        <h3 className="mb-2 text-[10px] font-semibold tracking-[0.08em] text-text-faint uppercase">
          Actions
        </h3>
        {/* Keyed on id + status: a finished escalate/resolve, or another ticket, starts a fresh form. */}
        <TicketActions
          key={`${ticket.id}:${ticket.status}`}
          ticket={ticket}
          departments={departments}
          onEscalate={onEscalate}
          onResolve={onResolve}
          error={actionError}
          acting={acting}
        />
      </div>
    </div>
  );
}
