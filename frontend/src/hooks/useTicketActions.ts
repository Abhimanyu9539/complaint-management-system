import { useCallback, useRef, useState } from 'react';
import { AdminRequestError } from '@/lib/admin/errors';
import { adminTransport } from '@/lib/admin/transport';
import type { DeptQuestion, DiscardReason, TicketDetail } from '@/lib/tickets/types';

export interface UseTicketActionsResult {
  detail: TicketDetail | null;
  detailLoading: boolean;
  /** Set when the last load or action was refused — by the network or the state machine. */
  actionError: string | null;
  acting: boolean;
  openTicket(ticketId: string): Promise<void>;
  /** A question drafted for the department, or null if drafting failed. Changes nothing. */
  draftQuestion(departmentId: string): Promise<DeptQuestion | null>;
  /** Email the question to the department and hand the ticket over. */
  escalate(departmentId: string, question: string, questionDraftId: string | null): Promise<void>;
  /** Save the department's answer; the draft is rewritten from it in the background. */
  recordDeptResponse(answer: string): Promise<void>;
  resolve(note: string): Promise<void>;
  /** Email the (possibly edited) draft to the customer; resolves the ticket. */
  sendReply(draftId: string, finalText: string): Promise<void>;
  discard(draftId: string, reason: DiscardReason, note: string): Promise<void>;
  regenerate(): Promise<void>;
  clear(): void;
}

/**
 * Escalate/resolve/open-detail, shared by `/admin/tickets` and the workbench
 * so the two surfaces cannot drift onto two different mirrors of the same
 * behaviour.
 *
 * `onChanged` fires after a successful escalate or resolve — never after a
 * plain `openTicket` — so the caller can refresh whichever list rendered the
 * row that changed (a queue, a table, an escalation summary) without this hook
 * needing to know what that list is.
 */
export function useTicketActions(onChanged?: () => void): UseTicketActionsResult {
  const [detail, setDetail] = useState<TicketDetail | null>(null);
  const [detailLoading, setDetailLoading] = useState(false);
  const [acting, setActing] = useState(false);
  const [actionError, setActionError] = useState<string | null>(null);

  // Exactly one detail fetch in flight: fast row-clicking aborts the loser
  // instead of letting it land after — and overwrite — a later click's result.
  const detailAbortRef = useRef<AbortController | null>(null);

  const openTicket = useCallback(async (ticketId: string) => {
    setActionError(null);
    setDetailLoading(true);
    detailAbortRef.current?.abort();
    const controller = new AbortController();
    detailAbortRef.current = controller;

    try {
      const result = await adminTransport.getTicket(ticketId, controller.signal);
      if (controller.signal.aborted) return;
      setDetail(result.data);
    } catch (err) {
      if (err instanceof DOMException && err.name === 'AbortError') return;
      console.warn('tickets: failed to load ticket detail', err);
      setDetail(null);
      setActionError(
        err instanceof AdminRequestError ? err.message : 'Could not load that ticket.',
      );
    } finally {
      // A stale (aborted) request's `finally` must not clear the *newer*
      // request's loading state.
      if (!controller.signal.aborted) setDetailLoading(false);
    }
  }, []);

  const runAction = useCallback(
    async (action: (signal: AbortSignal) => Promise<unknown>, ticketId: string) => {
      setActing(true);
      setActionError(null);
      const controller = new AbortController();
      try {
        await action(controller.signal);
        await openTicket(ticketId);
        onChanged?.();
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
    [openTicket, onChanged],
  );

  const draftQuestion = useCallback(
    async (departmentId: string): Promise<DeptQuestion | null> => {
      const ticketId = detail?.ticket.id;
      if (!ticketId) return null;
      try {
        const result = await adminTransport.draftDeptQuestion(
          ticketId,
          departmentId,
          new AbortController().signal,
        );
        return result.data;
      } catch (err) {
        // Not an action failure: the agent can still write the question by hand.
        console.warn('tickets: drafting the department question failed', err);
        return null;
      }
    },
    [detail],
  );

  const escalate = useCallback(
    async (departmentId: string, question: string, questionDraftId: string | null) => {
      const ticketId = detail?.ticket.id;
      if (!ticketId) return;
      await runAction(
        (signal) =>
          adminTransport.escalateTicket(
            ticketId,
            departmentId,
            question.trim(),
            questionDraftId,
            signal,
          ),
        ticketId,
      );
    },
    [detail, runAction],
  );

  const recordDeptResponse = useCallback(
    async (answer: string) => {
      const ticketId = detail?.ticket.id;
      if (!ticketId) return;
      await runAction(
        (signal) => adminTransport.recordDeptResponse(ticketId, answer.trim(), signal),
        ticketId,
      );
    },
    [detail, runAction],
  );

  const resolve = useCallback(
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

  const sendReply = useCallback(
    async (draftId: string, finalText: string) => {
      const ticketId = detail?.ticket.id;
      if (!ticketId) return;
      await runAction(
        (signal) => adminTransport.sendReply(ticketId, draftId, finalText, signal),
        ticketId,
      );
    },
    [detail, runAction],
  );

  const discard = useCallback(
    async (draftId: string, reason: DiscardReason, note: string) => {
      const ticketId = detail?.ticket.id;
      if (!ticketId) return;
      await runAction(
        (signal) =>
          adminTransport.discardDraft(ticketId, draftId, reason, note.trim() || null, signal),
        ticketId,
      );
    },
    [detail, runAction],
  );

  const regenerate = useCallback(async () => {
    const ticketId = detail?.ticket.id;
    if (!ticketId) return;
    await runAction((signal) => adminTransport.regenerateDraft(ticketId, signal), ticketId);
  }, [detail, runAction]);

  const clear = useCallback(() => {
    detailAbortRef.current?.abort();
    setDetail(null);
    setActionError(null);
  }, []);

  return {
    detail,
    detailLoading,
    actionError,
    acting,
    openTicket,
    draftQuestion,
    escalate,
    recordDeptResponse,
    resolve,
    sendReply,
    discard,
    regenerate,
    clear,
  };
}
