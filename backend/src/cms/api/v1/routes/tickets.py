"""Ticket intake and lifecycle — the API's first write endpoints.

Same dispatch rule as `admin.py`: every handler is sync `def`. The supabase
client is blocking, and a blocking call inside `async def` stalls the event loop
for every concurrent request.

Error shape is FastAPI's `{"detail": ...}`, matching the rest of the API. This
is the moment `admin.py`'s `TODO(lld.md §4)` anticipated — problem+json was to
be adopted "when the first write endpoints land" — and it is deliberately not
taken here: converting one router while six sibling endpoints keep the old shape
would leave clients parsing two error formats, which is worse than one uniform
format that is not yet the specified one. The TODO stays open, and moving it is
a single change across the whole API rather than a drip.

──────────────────────────────────────────────────────────────────────────────
⚠  `POST /tickets` IS AN UNAUTHENTICATED PUBLIC WRITE.

The whole API is unauthenticated (see `admin.py`), and it holds the Supabase
*service-role* key, which bypasses RLS entirely — the row-level policies on
`tickets` will not stop anything that reaches this handler. Exposing this to the
internet as it stands means anonymous inserts into `tickets` and anonymous
collection of customer email addresses.

What guards this today: bounded fields on `CreateTicketRequest` (a rejected
oversized body is a 422, not a multi-megabyte row) and nothing else. There is no
rate limit, no CAPTCHA, and no origin check beyond CORS, which is not a security
control.

The fix is `Depends(require_admin)` on the read/act routes plus a rate limiter
in front of the create route — see `backend/docs/admin-api.md` §9. Do not deploy
this publicly before both exist.
──────────────────────────────────────────────────────────────────────────────
"""

import logging
from typing import Literal

from fastapi import APIRouter, HTTPException, Query

from cms.schemas.tickets import (
    CreateTicketRequest,
    EscalateTicketRequest,
    ResolveTicketRequest,
    Ticket,
    TicketCreated,
    TicketDetail,
    TicketPage,
)
from cms.services import ticket_service
from cms.services.ticket_service import IllegalTransition, UnknownDepartment

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/tickets", tags=["tickets"])

UNAVAILABLE = "Tickets are unavailable right now. Check the server log."

# What a customer sees when the insert fails. Deliberately actionable: a
# complaint they typed and lost is the worst outcome this endpoint has, so the
# message tells them their text is still in the form.
CREATE_FAILED = (
    "We could not record your complaint just now. Your message has not been lost — "
    "please try again in a moment."
)


@router.post("", response_model=TicketCreated, status_code=201)
def create_ticket(payload: CreateTicketRequest) -> TicketCreated:
    """Open a ticket from the customer-facing form.

    201, not 200: this creates a resource and returns its identity. The customer
    reference is `ticket_no`, which the database assigns, so the row is read back
    rather than echoed from the request.

    Unlike the ingestion trigger — which returns 202 because the work happens
    later — the ticket genuinely exists by the time this responds. There is no
    background job: classification and drafting are a later phase, and a ticket
    at `new` is a complete, valid ticket.
    """
    try:
        return ticket_service.create_ticket(
            subject=payload.subject.strip(),
            body=payload.body.strip(),
            customer_email=payload.customer_email.strip().lower(),
            severity=payload.severity,
        )
    except Exception:
        logger.exception("Failed to create a ticket")
        raise HTTPException(status_code=503, detail=CREATE_FAILED) from None


@router.get("", response_model=TicketPage)
def list_tickets(
    status: Literal[
        "new",
        "processing",
        "drafted",
        "needs_review",
        "escalated",
        "dept_responded",
        "resolved",
        "processing_failed",
    ]
    | None = Query(None),
    severity: Literal["low", "normal", "high", "critical"] | None = Query(None),
    search: str | None = Query(None, max_length=200),
    limit: int = Query(25, ge=1, le=100),
    offset: int = Query(0, ge=0),
) -> TicketPage:
    """A page of the ticket queue, newest first."""
    try:
        return ticket_service.build_ticket_page(
            status=status, severity=severity, search=search, limit=limit, offset=offset
        )
    except Exception:
        logger.exception("Failed to list tickets")
        raise HTTPException(status_code=503, detail=UNAVAILABLE) from None


@router.get("/{ticket_id}", response_model=TicketDetail)
def get_ticket(ticket_id: str) -> TicketDetail:
    """One ticket plus its audit trail."""
    try:
        return ticket_service.get_ticket(ticket_id)
    except LookupError:
        raise HTTPException(status_code=404, detail="No such ticket.") from None
    except Exception:
        logger.exception("Failed to fetch ticket %s", ticket_id)
        raise HTTPException(status_code=503, detail=UNAVAILABLE) from None


@router.post("/{ticket_id}/escalate", response_model=Ticket)
def escalate_ticket(ticket_id: str, payload: EscalateTicketRequest) -> Ticket:
    """Hand a ticket to a specialist department (Path B).

    409 on an illegal transition, per lld.md §2. Not 400: the request is
    well-formed and would succeed against the same ticket in another state, so
    the conflict is with the resource, not the payload.
    """
    try:
        return ticket_service.escalate_ticket(ticket_id, payload.department_id, payload.note)
    except LookupError:
        raise HTTPException(status_code=404, detail="No such ticket.") from None
    except UnknownDepartment as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from None
    except IllegalTransition as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from None
    except Exception:
        logger.exception("Failed to escalate ticket %s", ticket_id)
        raise HTTPException(status_code=503, detail=UNAVAILABLE) from None


@router.post("/{ticket_id}/resolve", response_model=Ticket)
def resolve_ticket(ticket_id: str, payload: ResolveTicketRequest) -> Ticket:
    """Close a ticket, stamping `resolution_path`.

    The path is derived from the ticket's own history, not from the request —
    see `ticket_service._resolution_path_for`. This endpoint is what moves the
    escalation-rate metric, which is why it does not accept the value.
    """
    try:
        return ticket_service.resolve_ticket(ticket_id, payload.note)
    except LookupError:
        raise HTTPException(status_code=404, detail="No such ticket.") from None
    except IllegalTransition as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from None
    except Exception:
        logger.exception("Failed to resolve ticket %s", ticket_id)
        raise HTTPException(status_code=503, detail=UNAVAILABLE) from None
