"""File one incoming email: a new complaint, a department's answer, or a customer's reply."""

import logging
import re
from email.utils import parseaddr

from cms.config.settings import get_settings
from cms.db.repositories import departments, inbound_emails, tickets
from cms.schemas.emails import InboundEmailRequest, InboundEmailResult
from cms.services import escalation_service, ticket_service

logger = logging.getLogger(__name__)


def reply_text(text: str) -> str:
    """The reply above the quoted history: everything before the first quote-marker line."""
    markers = [re.compile(pattern) for pattern in get_settings().reply_quote_markers]
    kept = []
    for line in text.splitlines():
        if any(marker.match(line.strip()) for marker in markers):
            break
        kept.append(line)
    return "\n".join(kept).strip()


def _own_addresses() -> set[str]:
    settings = get_settings()
    return {parseaddr(settings.support_email_from)[1].lower(), settings.support_reply_to.lower()}


def _ticket_no(subject: str) -> int | None:
    match = re.search(get_settings().ticket_ref_pattern, subject)
    return int(match.group(1)) if match else None


def _ignored(reason: str, ticket: dict | None = None) -> tuple[InboundEmailResult, None]:
    return (
        InboundEmailResult(
            outcome="ignored",
            reason=reason,
            ticket_id=ticket["id"] if ticket else None,
            ticket_no=ticket["ticket_no"] if ticket else None,
        ),
        None,
    )


async def _new_ticket(email: InboundEmailRequest, sender: str) -> tuple[InboundEmailResult, str]:
    settings = get_settings()
    created = await ticket_service.create_ticket(
        subject=email.subject.strip()[: settings.email_subject_max_chars] or settings.email_subject_fallback,
        body=email.text.strip()[: settings.email_body_max_chars],
        customer_email=sender,
        severity=settings.email_ticket_severity,
        source="email",
    )
    result = InboundEmailResult(outcome="created", ticket_id=created.id, ticket_no=created.ticket_no)
    return result, "created"


async def _reply_to_ticket(
    email: InboundEmailRequest, sender: str, ticket_no: int, department: dict | None
) -> tuple[InboundEmailResult, str | None]:
    try:
        ticket = await tickets.fetch_ticket_by_no(ticket_no)
    except LookupError:
        return _ignored(f"no ticket T-{ticket_no}")

    reply = reply_text(email.text)
    if not reply:
        return _ignored("no reply text above the quoted message", ticket)

    found = {"ticket_id": ticket["id"], "ticket_no": ticket["ticket_no"]}
    if department:
        if ticket["status"] != "escalated" or ticket.get("escalated_dept") != department["id"]:
            return _ignored("ticket isn't waiting on this department", ticket)
        # The same two steps as POST /tickets/{id}/dept-response.
        await escalation_service.record_answer(ticket["id"], reply)
        await ticket_service.start_processing(ticket["id"], resume=False)
        return InboundEmailResult(outcome="dept_answer", **found), "dept_response"

    if sender == (ticket.get("customer_email") or "").lower():
        await ticket_service.record_customer_reply(ticket["id"], reply)
        return InboundEmailResult(outcome="customer_reply", **found), None

    return _ignored("sender is neither the customer nor the department", ticket)


async def _route(email: InboundEmailRequest, sender: str) -> tuple[InboundEmailResult, str | None]:
    if "@" not in sender:
        return _ignored("no sender address")
    if sender in _own_addresses():
        return _ignored("sent from our own address")
    if email.auto_submitted and email.auto_submitted.strip().lower() != "no":
        return _ignored(f"automatic reply (Auto-Submitted: {email.auto_submitted.strip()})")

    department = await departments.fetch_department_by_mailbox(sender)
    ticket_no = _ticket_no(email.subject)
    if ticket_no is not None:
        return await _reply_to_ticket(email, sender, ticket_no, department)
    if department:
        return _ignored("department email without a ticket reference")
    return await _new_ticket(email, sender)


async def ingest_email(email: InboundEmailRequest) -> tuple[InboundEmailResult, str | None]:
    """File one email and return the result, plus the ticket-graph trigger when a ticket needs drafting.

    The `inbound_emails` insert is the dedupe lock, so a re-posted email changes nothing.
    A failure after it is recorded on the row and re-raised; a retry then sees a duplicate,
    which is deliberate: a second attempt could open the same ticket twice.
    """
    sender = parseaddr(email.from_address)[1].strip().lower()
    email_id = await inbound_emails.claim_email(
        {
            "message_id": email.message_id,
            "from_address": sender or email.from_address,
            "subject": email.subject,
            "body_text": email.text,
        }
    )
    if email_id is None:
        return InboundEmailResult(outcome="duplicate", reason="already received"), None

    try:
        result, trigger = await _route(email, sender)
        await inbound_emails.finish_email(email_id, result.outcome, result.reason, result.ticket_id)
    except Exception as exc:
        logger.exception("Email %s from %s could not be filed", email.message_id, sender)
        try:
            await inbound_emails.finish_email(email_id, "ignored", f"error: {type(exc).__name__}: {exc}")
        except Exception:
            logger.exception("Email %s: could not record the failure", email.message_id)
        raise

    logger.info(
        "Email %s from %s: %s (T-%s) %s",
        email.message_id,
        sender,
        result.outcome,
        result.ticket_no,
        result.reason or "",
    )
    return result, trigger
