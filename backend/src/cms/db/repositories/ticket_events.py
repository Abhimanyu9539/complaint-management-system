"""Every read and write of the `ticket_events` table.

An append-only audit log: who did what to a ticket, and when. There is
deliberately no update or delete helper, and none should be added — migration
0016 withholds the UPDATE and DELETE policies for exactly that reason, and its
comment says so outright: "Do not 'fix' this by adding one."

The `event` column is free TEXT with no CHECK. The vocabulary lives in 0016's
comment and is mirrored by `EVENTS` below so callers have one spelling to use
rather than a string literal per call site.
"""

import logging

from cms.db.session import get_supabase

logger = logging.getLogger(__name__)

TABLE = "ticket_events"

EVENT_COLUMNS = "id,ticket_id,actor_id,event,payload,created_at"

# The vocabulary from migration 0016's comment. Not enforced by the database, so
# this is the only place it is written down in code.
EVENTS: tuple[str, ...] = (
    "created",
    "classified",
    "drafted",
    "sent",
    "escalated",
    "dept_responded",
    "resolved",
    "reopened",
    "assigned",
    "failed",
)


def append_event(
    ticket_id: str,
    event: str,
    payload: dict | None = None,
    actor_id: str | None = None,
) -> None:
    """Record one thing that happened to a ticket.

    Swallows its failure, uniquely in this package. Everywhere else a write that
    fails must surface, but the audit row is written *after* the state change it
    describes has already committed: raising here would report a failure for an
    escalation that did in fact happen, and the caller's only honest recovery
    would be to lie in the other direction. A missing audit row is a gap in the
    log; a false error is a gap in the operator's trust. The gap is logged at
    ERROR so it is still visible.
    """
    if event not in EVENTS:
        # Not fatal — the column has no CHECK, so an unknown event still writes.
        # Logged because it is almost always a typo rather than a new verb.
        logger.warning("Unrecognised ticket event %r for ticket %s", event, ticket_id)

    try:
        get_supabase().table(TABLE).insert(
            {
                "ticket_id": ticket_id,
                "event": event,
                "payload": payload or {},
                "actor_id": actor_id,
            }
        ).execute()
    except Exception:
        logger.exception(
            "Failed to append %r event for ticket %s — the state change itself succeeded",
            event,
            ticket_id,
        )


def list_events(ticket_id: str, limit: int = 200) -> list[dict]:
    """A ticket's history, oldest first — the drawer's timeline.

    Oldest first because a timeline is read forwards; the index on
    `(ticket_id, created_at)` serves this order directly.
    """
    try:
        response = (
            get_supabase()
            .table(TABLE)
            .select(EVENT_COLUMNS)
            .eq("ticket_id", ticket_id)
            .order("created_at", desc=False)
            .limit(limit)
            .execute()
        )
    except Exception:
        logger.exception("Failed to list %s rows for ticket %s", TABLE, ticket_id)
        raise
    return response.data or []
