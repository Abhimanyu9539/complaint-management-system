/**
 * The customer-facing ticket transport — one method, one POST.
 *
 * Separate from `lib/admin` on purpose. That module spreads a mock across every
 * method it cannot serve, which is right for an ops dashboard and wrong here: a
 * customer whose complaint was quietly simulated has lost it. So this transport
 * has no mock path at all. With no `VITE_API_BASE_URL` configured, `createTicket`
 * rejects with a message saying the form is not connected, rather than
 * pretending to succeed.
 *
 * Contract: `POST /api/v1/tickets` → 201. See `backend/docs/admin-api.md` §10.
 */

import type { CreateTicketRequest, TicketCreated } from './types';

const apiBaseUrl = import.meta.env.VITE_API_BASE_URL as string | undefined;

/** True when the form can actually reach a backend. Drives the offline notice. */
export const ticketsConfigured = Boolean(apiBaseUrl);

/**
 * A failed submission, carrying something the customer can act on.
 *
 * `fieldErrors` is populated from FastAPI's 422 body so a rejected field is
 * marked in place rather than reported as a general failure the customer has to
 * hunt through the form for.
 */
export class TicketRequestError extends Error {
  readonly status: number | null;
  readonly fieldErrors: Record<string, string>;

  constructor(message: string, status: number | null, fieldErrors: Record<string, string> = {}) {
    super(message);
    this.name = 'TicketRequestError';
    this.status = status;
    this.fieldErrors = fieldErrors;
  }
}

/** FastAPI's 422 shape: `{detail: [{loc: ['body', 'subject'], msg: '…'}]}`. */
interface ValidationItem {
  loc?: unknown[];
  msg?: string;
}

/**
 * Turn a 422 body into `{field: message}`.
 *
 * `loc` is `['body', '<field>']` for a request-model field, so the last element
 * is the name. Anything that does not match that shape is skipped rather than
 * guessed at — a mislabelled field error points the customer at the wrong input.
 */
function toFieldErrors(detail: unknown): Record<string, string> {
  if (!Array.isArray(detail)) return {};

  const errors: Record<string, string> = {};
  for (const raw of detail) {
    const item = raw as ValidationItem;
    const field = Array.isArray(item.loc) ? item.loc.at(-1) : undefined;
    if (typeof field === 'string' && typeof item.msg === 'string' && field !== 'body') {
      errors[field] = item.msg;
    }
  }
  return errors;
}

/** Maps the wire's snake_case onto the view model. */
interface WireCreated {
  id: string;
  ticket_no: number;
  status: TicketCreated['status'];
  created_at: string;
}

export async function createTicket(
  request: CreateTicketRequest,
  signal?: AbortSignal,
): Promise<TicketCreated> {
  if (!apiBaseUrl) {
    throw new TicketRequestError(
      'This form is not connected to a server yet, so your complaint cannot be submitted.',
      null,
    );
  }

  let response: Response;
  try {
    response = await fetch(`${apiBaseUrl}/api/v1/tickets`, {
      method: 'POST',
      signal,
      headers: { 'Content-Type': 'application/json', Accept: 'application/json' },
      body: JSON.stringify({
        subject: request.subject,
        body: request.body,
        customer_email: request.customerEmail,
        severity: request.severity,
      }),
    });
  } catch (err) {
    if (err instanceof DOMException && err.name === 'AbortError') throw err;
    console.warn('tickets: create request failed', err);
    throw new TicketRequestError(
      'We could not reach the server. Check your connection and try again — your message is still here.',
      null,
    );
  }

  if (!response.ok) {
    let detail: unknown;
    try {
      detail = ((await response.json()) as { detail?: unknown }).detail;
    } catch {
      // Unreadable body. The status alone still shapes a useful message.
    }

    if (response.status === 422) {
      const fieldErrors = toFieldErrors(detail);
      throw new TicketRequestError(
        Object.keys(fieldErrors).length > 0
          ? 'Please fix the highlighted fields.'
          : 'Some of the details were not accepted. Please review and try again.',
        422,
        fieldErrors,
      );
    }

    throw new TicketRequestError(
      typeof detail === 'string'
        ? detail
        : 'Something went wrong submitting your complaint. Please try again in a moment.',
      response.status,
    );
  }

  const wire = (await response.json()) as WireCreated;
  return {
    id: wire.id,
    ticketNo: wire.ticket_no,
    status: wire.status,
    createdAt: wire.created_at,
  };
}
