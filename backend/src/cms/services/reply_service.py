"""Act on a ticket's draft: send it to the customer by email, or discard it.

Every action writes one `draft_feedback` row — the flywheel's signal. The row
is written before the email goes out: `draft_id` is UNIQUE, so a second send of
the same draft fails there instead of mailing the customer twice.
"""

import logging
import re

from cms.config.settings import get_settings
from cms.db.repositories import draft_feedback, drafts, ticket_events, tickets
from cms.schemas.tickets import Ticket
from cms.services import ticket_service
from cms.services.email_sender import EmailSendError, send_email

logger = logging.getLogger(__name__)

# One or more [n] markers and the space before them: "covered [1][4]." -> "covered."
MARKERS = re.compile(r"\s*(?:\[\d+\])+")

# The draft is read-only while a department owns the ticket, and once it is closed.
DRAFT_LOCKED_STATUSES = ("escalated", "resolved")


class DraftConflict(Exception):
    """The draft can't be acted on: a newer one exists, it was handled, or it is only a holding reply."""


class InvalidReply(Exception):
    """The reply can't be sent as asked: no customer address, or nothing left to send."""


def strip_markers(text: str) -> str:
    """The reply as the customer reads it: every [n] source marker removed."""
    return MARKERS.sub("", text).strip()


def _normalise(text: str) -> str:
    return " ".join(text.split())


async def _actionable_draft(ticket: dict, draft_id: str) -> dict:
    """The draft, if the ticket is open to it, it is the latest, and nobody has acted on it yet."""
    ticket_id = ticket["id"]
    if ticket["status"] in DRAFT_LOCKED_STATUSES:
        raise DraftConflict(
            f"The ticket is {ticket['status']}, so its draft can't be sent or discarded."
        )

    draft = await drafts.fetch_draft(draft_id)
    if draft["ticket_id"] != ticket_id:
        raise LookupError(f"Draft {draft_id} does not belong to ticket {ticket_id}")

    latest = await drafts.fetch_latest_draft(ticket_id)
    if latest and latest["id"] != draft_id:
        raise DraftConflict("A newer draft exists. Reload the ticket.")
    if await draft_feedback.fetch_feedback(draft_id):
        raise DraftConflict("This draft was already sent or discarded.")
    return draft


async def send_reply(ticket_id: str, draft_id: str, final_text: str) -> Ticket:
    """Email the reply to the customer, record what was sent, and resolve the ticket."""
    ticket = await tickets.fetch_ticket(ticket_id)
    # Checked before anything is sent: a reply must not go out on a ticket that can't close.
    ticket_service.assert_transition(ticket["status"], "resolved")
    draft = await _actionable_draft(ticket, draft_id)

    to = ticket.get("customer_email")
    if not to:
        raise InvalidReply("This ticket has no customer email address.")
    body = strip_markers(final_text)
    if not body:
        raise InvalidReply("The reply is empty.")

    unedited = _normalise(body) == _normalise(strip_markers(draft["draft_text"]))
    if draft["no_match"] and unedited:
        raise DraftConflict(
            "This is only a holding reply. Write the resolution into it, or escalate the ticket."
        )
    action = "accepted" if unedited else "edited"

    feedback = await draft_feedback.insert_feedback(
        {"draft_id": draft_id, "user_id": None, "action": action, "final_text": body}
    )

    subject = get_settings().reply_subject_template.format(
        subject=ticket["subject"], ticket_no=ticket["ticket_no"]
    )
    try:
        message_id = await send_email(to, subject, body)
    except EmailSendError as exc:
        # Nothing left, so free the draft for a retry.
        try:
            await draft_feedback.delete_feedback(feedback["id"])
        except Exception:
            logger.exception("Ticket %s: the draft stays locked after a failed send", ticket_id)
        await ticket_events.append_event(ticket_id, "failed", {"stage": "send_email", "error": str(exc)})
        raise

    await ticket_events.append_event(
        ticket_id,
        "sent",
        {
            "draft_id": draft_id,
            "version": draft["version"],
            "action": action,
            "message_id": message_id,
            "to": to,
        },
    )
    logger.info("Ticket %s: reply sent (%s, draft v%d)", ticket_id, action, draft["version"])
    return await ticket_service.resolve_ticket(ticket_id)


async def discard_draft(ticket_id: str, draft_id: str, reason: str, note: str | None = None) -> Ticket:
    """Reject the draft with a reason. The ticket stays where it is; the agent regenerates or escalates."""
    ticket = await tickets.fetch_ticket(ticket_id)
    draft = await _actionable_draft(ticket, draft_id)

    await draft_feedback.insert_feedback(
        {"draft_id": draft_id, "user_id": None, "action": "rejected", "edit_reason": reason}
    )
    await ticket_events.append_event(
        ticket_id,
        "discarded",
        {"draft_id": draft_id, "version": draft["version"], "reason": reason, "note": note},
    )
    logger.info("Ticket %s: draft v%d discarded (%s)", ticket_id, draft["version"], reason)
    return ticket_service.to_ticket(ticket)
