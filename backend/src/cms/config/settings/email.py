"""Email: the outgoing SMTP reply, incoming mail from n8n and the screening of new mail."""

from pydantic import BaseModel


class EmailSettings(BaseModel):
    # --- Email (the reply to the customer) ---
    # Defaults point at Mailpit from docker-compose: it catches every message and delivers none.
    smtp_host: str = "localhost"
    smtp_port: int = 1025
    smtp_username: str | None = None
    smtp_password: str | None = None
    smtp_starttls: bool = False
    smtp_timeout_seconds: float = 10.0
    support_email_from: str = "Customer Care <support@example.com>"
    support_reply_to: str = "support@example.com"
    # The [T-n] tag matches an incoming reply to its ticket (`ticket_ref_pattern`).
    reply_subject_template: str = "Re: {subject} [T-{ticket_no}]"
    # The escalation email to a department. Its reply comes back to `support_reply_to`.
    dept_question_subject_template: str = "[T-{ticket_no}] Question from Customer Care: {subject}"
    dept_question_body_template: str = (
        "{question}\n\n"
        "---\n"
        "Complaint T-{ticket_no}: {subject}\n\n"
        "{body}\n\n"
        "Please reply to this email and keep [T-{ticket_no}] in the subject."
    )
    # Off, only a local SMTP server (Mailpit) is allowed. Sending needs a signed-in
    # agent, but a dev machine should still opt in before mail reaches real people.
    email_real_delivery_enabled: bool = False
    local_smtp_hosts: list[str] = ["localhost", "127.0.0.1", "mailpit"]

    # --- Incoming email (n8n posts each message to /api/v1/emails/inbound) ---
    # The shared secret n8n sends as `X-Inbound-Secret`. Unset turns inbound email off (503).
    inbound_email_secret: str | None = None
    # The ticket reference in a reply's subject; outgoing subjects carry it.
    ticket_ref_pattern: str = r"\[T-(\d+)\]"
    email_subject_fallback: str = "(no subject)"
    email_ticket_severity: str = "normal"
    # Same bounds as `CreateTicketRequest`.
    email_subject_max_chars: int = 200
    email_body_max_chars: int = 8000
    # Lines where quoted history starts in a reply; only the text above the first one is kept.
    reply_quote_markers: list[str] = [
        r"^On .+ wrote:$",
        r"^>",
        r"^-----Original Message-----",
        r"^From: ",
    ]

    # --- Screening a new email ---
    # A new email from one of these senders (the part before the @) is automated, not a customer.
    automated_sender_pattern: str = (
        r"^(no-?reply|do-?not-?reply|mailer-daemon|postmaster|notifications?|bounces?)([+._-].*)?@"
    )
    # `Precedence` values that mark bulk mail. Any `List-Unsubscribe` header does too.
    bulk_precedence_values: list[str] = ["bulk", "list", "junk"]
    # The model check on a new email that passed the rules above: is it a customer writing?
    email_screen_enabled: bool = True
    # How much of the body the check reads.
    email_screen_max_chars: int = 2000
