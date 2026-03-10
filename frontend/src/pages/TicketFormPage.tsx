import { CircleCheck, MessageSquareWarning, TriangleAlert } from 'lucide-react';
import { useState } from 'react';
import { Link } from 'react-router';
import { Button } from '@/components/ui/Button';
import { Select } from '@/components/ui/Select';
import { TextArea } from '@/components/ui/TextArea';
import { TextInput } from '@/components/ui/TextInput';
import { ThemeToggle } from '@/components/layout/ThemeToggle';
import { TICKET_LIMITS } from '@/lib/tickets/types';
import { TicketRequestError, createTicket, ticketsConfigured } from '@/lib/tickets/transport';
import type { CustomerSeverity, TicketCreated } from '@/lib/tickets/types';

const SEVERITY_OPTIONS = [
  { value: 'low', label: 'Low — a minor issue' },
  { value: 'normal', label: 'Normal — needs attention' },
  { value: 'high', label: 'High — blocking me right now' },
];

type FieldErrors = Partial<Record<'subject' | 'body' | 'customer_email', string>>;

/**
 * Client-side validation, mirroring `schemas/tickets.py`.
 *
 * Duplicated on purpose. The server's copy is the one that decides — a client
 * check is a courtesy, not a control — but a customer who has typed a complaint
 * should learn that the subject is too short before the round trip, not after
 * it. The server still rejects anything this misses.
 */
function validate(subject: string, body: string, email: string): FieldErrors {
  const errors: FieldErrors = {};

  if (subject.trim().length < TICKET_LIMITS.subjectMin) {
    errors.subject = `Please give a subject of at least ${TICKET_LIMITS.subjectMin} characters.`;
  }
  if (body.trim().length < TICKET_LIMITS.bodyMin) {
    errors.body = `Please describe what happened — at least ${TICKET_LIMITS.bodyMin} characters.`;
  }
  if (!/^[^@\s]+@[^@\s]+\.[^@\s]+$/.test(email.trim())) {
    errors.customer_email = 'Please enter an email address we can reply to.';
  }
  return errors;
}

/**
 * The customer complaint form.
 *
 * Public and standalone: this route deliberately does not mount `ChatProvider`,
 * which fires `listSessions()` on mount and would make a stranger's first page
 * load fetch an agent's chat history.
 *
 * Nothing here is ever simulated. `lib/tickets/transport` has no mock path, so
 * an unconfigured build says so in a banner rather than accepting a complaint
 * into nowhere.
 */
export function TicketFormPage() {
  const [subject, setSubject] = useState('');
  const [body, setBody] = useState('');
  const [email, setEmail] = useState('');
  const [severity, setSeverity] = useState<CustomerSeverity>('normal');

  const [errors, setErrors] = useState<FieldErrors>({});
  const [formError, setFormError] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);
  const [created, setCreated] = useState<TicketCreated | null>(null);

  async function handleSubmit() {
    setFormError(null);

    const found = validate(subject, body, email);
    if (Object.keys(found).length > 0) {
      setErrors(found);
      return;
    }
    setErrors({});
    setSubmitting(true);

    try {
      const result = await createTicket({
        subject: subject.trim(),
        body: body.trim(),
        customerEmail: email.trim(),
        severity,
      });

      // Clear only after the server confirms. Clearing optimistically and then
      // failing would delete what the customer wrote, which is the single worst
      // thing this page can do.
      setCreated(result);
      setSubject('');
      setBody('');
      setEmail('');
      setSeverity('normal');
    } catch (err) {
      if (err instanceof TicketRequestError) {
        setErrors(err.fieldErrors as FieldErrors);
        setFormError(err.message);
      } else {
        console.error('tickets: unexpected submit failure', err);
        setFormError('Something went wrong. Please try again in a moment.');
      }
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <div className="flex h-full min-h-0 flex-col bg-bg">
      <header className="flex h-13 shrink-0 items-center justify-between gap-2 border-b border-border px-4">
        <Link to="/" className="flex min-w-0 items-center gap-2">
          <div className="flex h-6 w-6 shrink-0 items-center justify-center rounded-md bg-accent text-accent-text">
            <span className="font-display text-[13px] leading-none">R</span>
          </div>
          <span className="truncate font-display text-[14px] font-medium text-text">Support</span>
        </Link>
        <ThemeToggle />
      </header>

      <main className="min-h-0 flex-1 overflow-y-auto">
        <div className="mx-auto flex w-full max-w-2xl flex-col gap-5 p-4 sm:p-6">
          <div>
            <h1 className="font-display text-[22px] leading-tight font-medium text-text">
              Tell us what went wrong
            </h1>
            <p className="mt-1.5 text-[13px] leading-relaxed text-text-muted">
              We will read every word. Give us as much detail as you can — the more specific you
              are, the faster we can put it right.
            </p>
          </div>

          {!ticketsConfigured && (
            <div className="flex items-start gap-2.5 rounded-xl border border-warn/30 bg-warn-soft px-3.5 py-3">
              <TriangleAlert size={16} strokeWidth={1.75} className="mt-px shrink-0 text-warn" />
              <p className="text-[12px] leading-relaxed text-warn">
                This form is not connected to a server in this build, so nothing you type here can
                be submitted. Set <code>VITE_API_BASE_URL</code> to enable it.
              </p>
            </div>
          )}

          {created && <SubmittedNotice created={created} onDismiss={() => setCreated(null)} />}

          <form
            className="flex flex-col gap-4 rounded-xl border border-border bg-surface p-4 shadow-card sm:p-5"
            onSubmit={(event) => {
              event.preventDefault();
              void handleSubmit();
            }}
            noValidate
          >
            <TextInput
              label="Subject"
              value={subject}
              onChange={setSubject}
              error={errors.subject}
              hint="One line summarising the problem."
              placeholder="Replacement part arrived damaged"
              maxLength={TICKET_LIMITS.subjectMax}
              autoComplete="off"
              required
            />

            <TextArea
              label="What happened"
              value={body}
              onChange={setBody}
              error={errors.body}
              hint="Order numbers, dates, product names and any error messages all help."
              placeholder="I ordered a replacement hinge on 14 March. It arrived on the 19th with the mounting bracket already cracked…"
              maxLength={TICKET_LIMITS.bodyMax}
              rows={8}
              required
            />

            <TextInput
              label="Your email"
              type="email"
              value={email}
              onChange={setEmail}
              error={errors.customer_email}
              hint="We will only use this to reply to this complaint."
              placeholder="you@example.com"
              maxLength={TICKET_LIMITS.emailMax}
              autoComplete="email"
              required
            />

            <Select
              label="How urgent is this?"
              size="md"
              value={severity}
              onChange={(value) => setSeverity(value as CustomerSeverity)}
              options={SEVERITY_OPTIONS}
            />

            {formError && (
              <p
                role="alert"
                className="rounded-lg border border-danger/30 bg-danger-soft px-3 py-2 text-[12px] leading-relaxed text-danger"
              >
                {formError}
              </p>
            )}

            <div className="flex items-center justify-between gap-3 border-t border-border pt-4">
              <p className="text-[11px] leading-relaxed text-text-faint">
                You will get a reference number as soon as this is submitted.
              </p>
              {/* type="submit" overrides Button's default type="button", so
                  Enter inside a text field submits the form as expected. */}
              <Button type="submit" variant="primary" loading={submitting} disabled={submitting}>
                {submitting ? 'Submitting…' : 'Submit complaint'}
              </Button>
            </div>
          </form>
        </div>
      </main>
    </div>
  );
}

/**
 * The receipt.
 *
 * `T-{ticketNo}` is the whole point: `ticket_no` is assigned by the database,
 * so this is the first moment either side knows the reference, and a customer
 * without one has no way to ask about their complaint again.
 */
function SubmittedNotice({
  created,
  onDismiss,
}: {
  created: TicketCreated;
  onDismiss: () => void;
}) {
  return (
    <div
      role="status"
      className="flex items-start gap-3 rounded-xl border border-ok/30 bg-ok-soft px-4 py-3.5"
    >
      <CircleCheck size={18} strokeWidth={1.75} className="mt-px shrink-0 text-ok" />
      <div className="min-w-0 flex-1">
        <p className="text-[13px] font-semibold text-ok">
          Your complaint is with us — reference{' '}
          <span className="tabular-nums">T-{created.ticketNo}</span>
        </p>
        <p className="mt-1 text-[12px] leading-relaxed text-ok/90">
          Quote that number if you need to follow up. A member of the team will review it and reply
          to the address you gave.
        </p>
        <button
          type="button"
          onClick={onDismiss}
          className="mt-2 inline-flex items-center gap-1.5 text-[12px] font-medium text-ok underline-offset-2 hover:underline"
        >
          <MessageSquareWarning size={13} strokeWidth={2} />
          Report something else
        </button>
      </div>
    </div>
  );
}
