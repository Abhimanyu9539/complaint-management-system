"""The ticket lifecycle — creation, escalation, resolution.

Owns two things nothing else may duplicate:

1. **The state machine** from lld.md §2. `ALLOWED` below is that diagram as a
   table, and `transition()` is the only function permitted to change a ticket's
   status. An illegal move raises `IllegalTransition`, which the route layer maps
   to 409 Conflict — as lld.md specifies, and not 400: the request is well-formed,
   it is the ticket's current state that refuses it.

2. **How `resolution_path` is decided.** It is derived, never supplied. See
   `_resolution_path_for`.

Layering is the same as `admin_stats`: repositories return raw dicts, the
`_to_*` adapters here are the only place their keys are read, and everything
downstream of an adapter handles Pydantic models.
"""

import asyncio
import logging

from cms.db.repositories import departments, draft_feedback, drafts, ticket_events, tickets
from cms.schemas.tickets import (
    DraftFeedback,
    Ticket,
    TicketCreated,
    TicketDetail,
    TicketDraft,
    TicketEvent,
    TicketPage,
)

logger = logging.getLogger(__name__)


class IllegalTransition(Exception):
    """A status change the state machine forbids. Maps to 409 Conflict."""

    def __init__(self, current: str, target: str) -> None:
        super().__init__(
            f"A ticket at '{current}' cannot move to '{target}'."
        )
        self.current = current
        self.target = target


class UnknownDepartment(Exception):
    """An escalation target outside the closed set of twelve. Maps to 422."""


# lld.md §2, verbatim as a table. Every edge in that diagram appears here;
# statuses with no outgoing edge are still listed with an empty set so that a
# new status added to the CHECK constraint fails loudly here rather than
# silently permitting nothing.
#
# `processing` and the three statuses after it are written by the ticket
# pipeline: `start_processing` on the way in, the gate (`finish_processing`) on
# the way out. `drafted` and `needs_review` may go back to `processing` so a
# ticket can be drafted again (Regenerate, `cms-triage`). A ticket with a
# department's answer is redrafted from it and comes back to `dept_responded`.
ALLOWED: dict[str, frozenset[str]] = {
    "new": frozenset({"processing", "escalated", "resolved"}),
    "processing": frozenset({"drafted", "needs_review", "dept_responded", "processing_failed"}),
    "drafted": frozenset({"escalated", "resolved", "processing"}),
    "needs_review": frozenset({"escalated", "resolved", "processing"}),
    "escalated": frozenset({"dept_responded", "resolved"}),
    "dept_responded": frozenset({"escalated", "resolved", "processing"}),
    # Reopening: lld.md has resolved → drafted; a customer's email reply reopens to needs_review.
    "resolved": frozenset({"drafted", "needs_review"}),
    "processing_failed": frozenset({"processing"}),
}


def assert_transition(current: str, target: str) -> None:
    """Raise unless `current → target` is an edge in the machine."""
    if target not in ALLOWED.get(current, frozenset()):
        raise IllegalTransition(current, target)


def _resolution_path_for(row: dict) -> str:
    """Which path resolved this ticket: 'direct' or 'escalated'.

    Derived from `escalated_dept` rather than from the status history. The
    escalate action is the only writer of that column, so a non-null value means
    a department was involved at some point, which is exactly the definition of
    Path B — and it stays true after the ticket moves on to `dept_responded`,
    where the status alone no longer says how it got there.

    This is the whole of the escalation-rate definition. It lives in one
    function so that changing what counts as an escalation is a one-line change
    with one place to review, rather than a hunt through the routes.
    """
    return "escalated" if row.get("escalated_dept") else "direct"


# ---------------------------------------------------------------------------
# Adapters
# ---------------------------------------------------------------------------


def to_ticket(row: dict) -> Ticket:
    return Ticket(
        id=row["id"],
        ticket_no=row["ticket_no"],
        status=row["status"],
        severity=row["severity"],
        subject=row["subject"],
        body=row.get("body"),
        source=row.get("source") or "web",
        customer_email=row.get("customer_email"),
        predicted_dept=row.get("predicted_dept"),
        dept_confidence=row.get("dept_confidence"),
        escalated_dept=row.get("escalated_dept"),
        category=row.get("category"),
        entities=row.get("entities") or {},
        suggested_severity=row.get("suggested_severity"),
        dept_candidates=row.get("dept_candidates") or [],
        review_reasons=row.get("review_reasons") or [],
        resolution_path=row.get("resolution_path"),
        created_at=row["created_at"],
        updated_at=row["updated_at"],
        resolved_at=row.get("resolved_at"),
    )


def _to_event(row: dict) -> TicketEvent:
    return TicketEvent(
        id=row["id"],
        event=row["event"],
        payload=row.get("payload") or {},
        actor_id=row.get("actor_id"),
        created_at=row["created_at"],
    )


def _to_draft(row: dict, feedback: dict | None = None) -> TicketDraft:
    return TicketDraft(
        id=row["id"],
        version=row["version"],
        draft_text=row["draft_text"],
        no_match=row.get("no_match", False),
        grounded=row.get("grounded"),
        guard_reasons=row.get("guard_reasons") or [],
        retrieved_cases=row.get("retrieved_cases") or [],
        policy_refs=row.get("policy_refs") or [],
        guidance_refs=row.get("guidance_refs") or [],
        model=row["model"],
        prompt_version=row["prompt_version"],
        created_at=row["created_at"],
        feedback=DraftFeedback(
            action=feedback["action"],
            final_text=feedback.get("final_text"),
            edit_reason=feedback.get("edit_reason"),
            created_at=feedback["created_at"],
        )
        if feedback
        else None,
    )


async def _latest_draft(ticket_id: str) -> TicketDraft | None:
    """The ticket's latest draft, or None. A failed read must not take the ticket down with it."""
    try:
        row = await drafts.fetch_latest_draft(ticket_id)
        if not row:
            return None
        return _to_draft(row, await draft_feedback.fetch_feedback(row["id"]))
    except Exception:
        logger.exception("Could not read the draft for ticket %s; showing the ticket without it", ticket_id)
        return None


# ---------------------------------------------------------------------------
# Commands
# ---------------------------------------------------------------------------


async def create_ticket(
    *,
    subject: str,
    body: str,
    customer_email: str,
    severity: str,
    source: str = "web",
) -> TicketCreated:
    """Open a new ticket from the customer-facing form.

    `status` is left to the column default (`new`) rather than sent explicitly,
    so the database stays the single definition of where a ticket starts.
    """
    row = await tickets.create_ticket(
        {
            "subject": subject,
            "body": body,
            "customer_email": customer_email,
            "severity": severity,
            "source": source,
        }
    )

    # After the insert commits, never before: an audit row for a ticket that
    # failed to insert would describe something that did not happen.
    await ticket_events.append_event(row["id"], "created", {"source": source, "severity": severity})

    logger.info("Ticket %s created (T-%s) from %s", row["id"], row["ticket_no"], source)
    return TicketCreated(
        id=row["id"],
        ticket_no=row["ticket_no"],
        status=row["status"],
        created_at=row["created_at"],
    )


async def start_processing(ticket_id: str, resume: bool = True) -> dict:
    """Move a ticket to `processing` before the pipeline runs, and return its row.

    With `resume`, a ticket already at `processing` is returned unchanged: the
    Regenerate route moved it there before queueing the run, and a run that died
    half-way can be recovered with `cms-triage`. Without it, `processing` is
    refused, so a second Regenerate click can't start a parallel run. Raises
    `IllegalTransition` for a ticket a person has already escalated or resolved.
    """
    row = await tickets.fetch_ticket(ticket_id)
    if row["status"] == "processing" and resume:
        logger.info("Ticket %s is already processing; continuing", ticket_id)
        return row

    assert_transition(row["status"], "processing")
    return await tickets.update_ticket(ticket_id, {"status": "processing", "review_reasons": []})


async def finish_processing(ticket_id: str, status: str, reasons: list[str]) -> None:
    """The run's outcome: `drafted`, `needs_review`, `dept_responded` or `processing_failed`, with the reasons."""
    current = await tickets.fetch_ticket(ticket_id)
    assert_transition(current["status"], status)

    await tickets.update_ticket(ticket_id, {"status": status, "review_reasons": reasons})
    await ticket_events.append_event(ticket_id, "gated", {"status": status, "reasons": reasons})
    logger.info("Ticket %s gated to %s: %s", ticket_id, status, reasons)


async def get_department(department_id: str) -> dict:
    """The department, or `UnknownDepartment` (a 422) when it is not one of the twelve.

    The FK would reject a bad value anyway, but as a PostgREST error surfacing
    as a 500 — checking first turns that into a 422 that names the problem.
    """
    try:
        return await departments.fetch_department(department_id)
    except LookupError:
        raise UnknownDepartment(f"'{department_id}' is not one of the departments.") from None


async def escalate_ticket(
    ticket_id: str,
    department_id: str,
    note: str | None = None,
    email: dict | None = None,
    actor_id: str | None = None,
) -> Ticket:
    """Hand a ticket to a specialist department (Path B).

    `email` describes the question already sent to the department (`to`,
    `message_id`, ...) and goes on the `escalated` event with the note.
    `actor_id` is the agent who escalated; None means the system did.
    """
    await get_department(department_id)

    current = await tickets.fetch_ticket(ticket_id)
    assert_transition(current["status"], "escalated")

    row = await tickets.update_ticket(
        ticket_id,
        {"status": "escalated", "escalated_dept": department_id},
    )
    await ticket_events.append_event(
        ticket_id,
        "escalated",
        {
            "department_id": department_id,
            "note": note,
            "from_status": current["status"],
            **(email or {}),
        },
        actor_id=actor_id,
    )

    logger.info("Ticket %s escalated to %s", ticket_id, department_id)
    return to_ticket(row)


async def mark_dept_responded(ticket_id: str, response: dict, actor_id: str | None = None) -> Ticket:
    """Record that the escalated department answered. The redraft runs after this.

    `actor_id` is the agent who pasted the answer; None when it arrived by email.
    """
    current = await tickets.fetch_ticket(ticket_id)
    assert_transition(current["status"], "dept_responded")

    row = await tickets.update_ticket(ticket_id, {"status": "dept_responded"})
    await ticket_events.append_event(
        ticket_id,
        "dept_responded",
        {
            "dept_response_id": response["id"],
            "department_id": response["department_id"],
            "answer": response["answer_text"],
        },
        actor_id=actor_id,
    )

    logger.info("Ticket %s: %s answered", ticket_id, response["department_id"])
    return to_ticket(row)


async def resolve_ticket(
    ticket_id: str, note: str | None = None, actor_id: str | None = None
) -> Ticket:
    """Close a ticket and stamp the path it took.

    The path is read off the ticket, not off the request — see
    `_resolution_path_for`. A client that could assert its own path could set
    the north-star metric by hand.
    """
    current = await tickets.fetch_ticket(ticket_id)
    assert_transition(current["status"], "resolved")

    path = _resolution_path_for(current)
    row = await tickets.mark_resolved(ticket_id, path)
    await ticket_events.append_event(
        ticket_id,
        "resolved",
        {"resolution_path": path, "note": note, "from_status": current["status"]},
        actor_id=actor_id,
    )

    logger.info("Ticket %s resolved via the %s path", ticket_id, path)
    return to_ticket(row)


async def record_customer_reply(ticket_id: str, text: str) -> None:
    """Record a customer's email reply. A resolved ticket reopens to `needs_review`; nothing is redrafted."""
    current = await tickets.fetch_ticket(ticket_id)
    await ticket_events.append_event(ticket_id, "customer_replied", {"text": text})

    if current["status"] != "resolved":
        logger.info("Ticket %s: customer replied (status %s unchanged)", ticket_id, current["status"])
        return

    # The path and time are cleared so the escalation metrics stop counting it as resolved.
    assert_transition("resolved", "needs_review")
    await tickets.update_ticket(
        ticket_id,
        {
            "status": "needs_review",
            "review_reasons": ["Customer replied after resolution."],
            "resolution_path": None,
            "resolved_at": None,
        },
    )
    await ticket_events.append_event(ticket_id, "reopened", {"from_status": "resolved"})
    logger.info("Ticket %s reopened: the customer replied after resolution", ticket_id)


# ---------------------------------------------------------------------------
# Queries
# ---------------------------------------------------------------------------


async def get_ticket(ticket_id: str) -> TicketDetail:
    """One ticket, its whole audit trail and its latest draft — the drawer's single request.

    The three reads are independent, so they go out together. `fetch_ticket` still
    raises `LookupError` for a missing id and `gather` propagates it unchanged,
    so the route's 404 mapping is unaffected.
    """
    row, events, draft = await asyncio.gather(
        tickets.fetch_ticket(ticket_id),
        ticket_events.list_events(ticket_id),
        _latest_draft(ticket_id),
    )
    return TicketDetail(
        ticket=to_ticket(row),
        events=[_to_event(event) for event in events],
        draft=draft,
    )


async def build_ticket_page(
    *,
    status: str | None,
    severity: str | None,
    search: str | None,
    limit: int,
    offset: int,
) -> TicketPage:
    """A filtered, paged slice of the queue."""
    rows, total = await tickets.list_tickets(
        status=status,
        severity=severity,
        search=search,
        limit=limit,
        offset=offset,
    )
    return TicketPage(
        items=[to_ticket(row) for row in rows],
        total=total,
        limit=limit,
        offset=offset,
    )
