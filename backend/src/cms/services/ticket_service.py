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

from cms.db.repositories import departments, ticket_events, tickets
from cms.schemas.tickets import (
    Ticket,
    TicketCreated,
    TicketDetail,
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
# `processing`, `drafted`, `needs_review` and `processing_failed` have no writer
# yet — they belong to the drafting pipeline, which does not exist. They are
# kept because deleting them would mean re-deriving the machine later from a
# diagram, and a state machine with holes is worse than one with unused states.
ALLOWED: dict[str, frozenset[str]] = {
    "new": frozenset({"processing", "escalated", "resolved"}),
    "processing": frozenset({"drafted", "needs_review", "processing_failed"}),
    "drafted": frozenset({"escalated", "resolved"}),
    "needs_review": frozenset({"escalated", "resolved"}),
    "escalated": frozenset({"dept_responded", "resolved"}),
    "dept_responded": frozenset({"escalated", "resolved"}),
    # Reopening: lld.md has resolved → drafted when a customer replies again.
    "resolved": frozenset({"drafted"}),
    "processing_failed": frozenset({"processing"}),
}


def _assert_transition(current: str, target: str) -> None:
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


def _to_ticket(row: dict) -> Ticket:
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


async def escalate_ticket(ticket_id: str, department_id: str, note: str | None = None) -> Ticket:
    """Hand a ticket to a specialist department (Path B).

    The department is validated against the closed set before the write. The FK
    would reject a bad value anyway, but as a PostgREST error surfacing as a 500
    — checking first turns that into a 422 that names the problem.
    """
    valid = {row["id"] for row in await departments.list_departments()}
    if department_id not in valid:
        raise UnknownDepartment(f"'{department_id}' is not one of the {len(valid)} departments.")

    current = await tickets.fetch_ticket(ticket_id)
    _assert_transition(current["status"], "escalated")

    row = await tickets.update_ticket(
        ticket_id,
        {"status": "escalated", "escalated_dept": department_id},
    )
    await ticket_events.append_event(
        ticket_id,
        "escalated",
        {"department_id": department_id, "note": note, "from_status": current["status"]},
    )

    logger.info("Ticket %s escalated to %s", ticket_id, department_id)
    return _to_ticket(row)


async def resolve_ticket(ticket_id: str, note: str | None = None) -> Ticket:
    """Close a ticket and stamp the path it took.

    The path is read off the ticket, not off the request — see
    `_resolution_path_for`. A client that could assert its own path could set
    the north-star metric by hand.
    """
    current = await tickets.fetch_ticket(ticket_id)
    _assert_transition(current["status"], "resolved")

    path = _resolution_path_for(current)
    row = await tickets.mark_resolved(ticket_id, path)
    await ticket_events.append_event(
        ticket_id,
        "resolved",
        {"resolution_path": path, "note": note, "from_status": current["status"]},
    )

    logger.info("Ticket %s resolved via the %s path", ticket_id, path)
    return _to_ticket(row)


# ---------------------------------------------------------------------------
# Queries
# ---------------------------------------------------------------------------


async def get_ticket(ticket_id: str) -> TicketDetail:
    """One ticket and its whole audit trail — the drawer's single request.

    The two reads are independent, so they go out together. `fetch_ticket` still
    raises `LookupError` for a missing id and `gather` propagates it unchanged,
    so the route's 404 mapping is unaffected.
    """
    row, events = await asyncio.gather(
        tickets.fetch_ticket(ticket_id),
        ticket_events.list_events(ticket_id),
    )
    return TicketDetail(
        ticket=_to_ticket(row),
        events=[_to_event(event) for event in events],
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
        items=[_to_ticket(row) for row in rows],
        total=total,
        limit=limit,
        offset=offset,
    )
