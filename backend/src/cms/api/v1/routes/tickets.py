"""Ticket intake and lifecycle — the API's first write endpoints.

Same dispatch rule as `admin.py`: every handler is `async def` over an awaited
supabase `AsyncClient`, so concurrent requests share the event loop instead of
occupying a threadpool worker each.

Error shape is FastAPI's `{"detail": ...}`, matching the rest of the API. This
is the moment `admin.py`'s `TODO(lld.md §4)` anticipated — problem+json was to
be adopted "when the first write endpoints land" — and it is deliberately not
taken here: converting one router while six sibling endpoints keep the old shape
would leave clients parsing two error formats, which is worse than one uniform
format that is not yet the specified one. The TODO stays open, and moving it is
a single change across the whole API rather than a drip.

Access: every route needs a signed-in agent (`get_current_user`), except
`POST /tickets`, the customer form, which is public by design. Routes that act
on a ticket record the agent as the event's actor.

⚠ `POST /tickets` is still an unauthenticated write with no rate limit: only the
bounded fields on `CreateTicketRequest` guard it. Put a rate limiter in front of
it before deploying publicly.
"""

import logging
from typing import Literal

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query

from cms.api.deps import get_current_user
from cms.schemas.auth import CurrentUser
from cms.schemas.tickets import (
    CreateTicketRequest,
    DeptQuestion,
    DeptResponseRequest,
    DiscardDraftRequest,
    DraftDeptQuestionRequest,
    EscalateTicketRequest,
    ResolveTicketRequest,
    SendReplyRequest,
    Ticket,
    TicketCreated,
    TicketDetail,
    TicketPage,
)
from cms.services import (
    case_minting,
    escalation_service,
    reply_service,
    ticket_pipeline,
    ticket_service,
)
from cms.services.email_sender import EmailSendError
from cms.services.reply_service import DraftConflict, InvalidReply
from cms.services.ticket_service import IllegalTransition, UnknownDepartment

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/tickets", tags=["tickets"])

UNAVAILABLE = "Tickets are unavailable right now. Check the server log."

# The email did not leave, and nothing was recorded, so a retry is safe.
SEND_FAILED = "The email could not be sent. Nothing was recorded — try again in a moment."

QUESTION_FAILED = "Could not draft a question. Write it yourself, or try again in a moment."

# What a customer sees when the insert fails. Deliberately actionable: a
# complaint they typed and lost is the worst outcome this endpoint has, so the
# message tells them their text is still in the form.
CREATE_FAILED = (
    "We could not record your complaint just now. Your message has not been lost — "
    "please try again in a moment."
)


@router.post("", response_model=TicketCreated, status_code=201)
async def create_ticket(
    payload: CreateTicketRequest, background_tasks: BackgroundTasks
) -> TicketCreated:
    """Open a ticket from the customer-facing form.

    201, not 200: this creates a resource and returns its identity. The customer
    reference is `ticket_no`, which the database assigns, so the row is read back
    rather than echoed from the request.

    The ticket exists by the time this responds. The ticket graph then runs in
    the background (`ticket_pipeline.process_ticket`) and adds the
    classification and a draft reply; the customer does not wait for it, and a ticket it never
    reaches is still a complete ticket at `new`.
    """
    try:
        created = await ticket_service.create_ticket(
            subject=payload.subject.strip(),
            body=payload.body.strip(),
            customer_email=payload.customer_email.strip().lower(),
            severity=payload.severity,
        )
    except Exception:
        logger.exception("Failed to create a ticket")
        raise HTTPException(status_code=503, detail=CREATE_FAILED) from None

    background_tasks.add_task(ticket_pipeline.process_ticket, created.id)
    return created


@router.get("", response_model=TicketPage, dependencies=[Depends(get_current_user)])
async def list_tickets(
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
        return await ticket_service.build_ticket_page(
            status=status, severity=severity, search=search, limit=limit, offset=offset
        )
    except Exception:
        logger.exception("Failed to list tickets")
        raise HTTPException(status_code=503, detail=UNAVAILABLE) from None


@router.get("/{ticket_id}", response_model=TicketDetail, dependencies=[Depends(get_current_user)])
async def get_ticket(ticket_id: str) -> TicketDetail:
    """One ticket plus its audit trail."""
    try:
        return await ticket_service.get_ticket(ticket_id)
    except LookupError:
        raise HTTPException(status_code=404, detail="No such ticket.") from None
    except Exception:
        logger.exception("Failed to fetch ticket %s", ticket_id)
        raise HTTPException(status_code=503, detail=UNAVAILABLE) from None


@router.post(
    "/{ticket_id}/dept-question", response_model=DeptQuestion, dependencies=[Depends(get_current_user)]
)
async def draft_dept_question(ticket_id: str, payload: DraftDeptQuestionRequest) -> DeptQuestion:
    """Draft the question to send the department. Nothing is sent or changed on the ticket."""
    try:
        return await escalation_service.draft_question(ticket_id, payload.department_id)
    except LookupError:
        raise HTTPException(status_code=404, detail="No such ticket.") from None
    except UnknownDepartment as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from None
    except IllegalTransition as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from None
    except Exception:
        logger.exception("Failed to draft the department question for ticket %s", ticket_id)
        raise HTTPException(status_code=503, detail=QUESTION_FAILED) from None


@router.post("/{ticket_id}/escalate", response_model=Ticket)
async def escalate_ticket(
    ticket_id: str,
    payload: EscalateTicketRequest,
    user: CurrentUser = Depends(get_current_user),
) -> Ticket:
    """Email the question to a specialist department and hand the ticket over (Path B).

    409 on an illegal transition, per lld.md §2. Not 400: the request is
    well-formed and would succeed against the same ticket in another state, so
    the conflict is with the resource, not the payload. 502 when the email fails.
    """
    try:
        return await escalation_service.escalate(
            ticket_id, payload.department_id, payload.note, payload.question_draft_id, user.id
        )
    except LookupError:
        raise HTTPException(status_code=404, detail="No such ticket.") from None
    except UnknownDepartment as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from None
    except IllegalTransition as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from None
    except EmailSendError:
        raise HTTPException(status_code=502, detail=SEND_FAILED) from None
    except Exception:
        logger.exception("Failed to escalate ticket %s", ticket_id)
        raise HTTPException(status_code=503, detail=UNAVAILABLE) from None


@router.post("/{ticket_id}/dept-response", response_model=Ticket, status_code=202)
async def record_dept_response(
    ticket_id: str,
    payload: DeptResponseRequest,
    background_tasks: BackgroundTasks,
    user: CurrentUser = Depends(get_current_user),
) -> Ticket:
    """Save the department's answer; the ticket graph then redrafts from it in the background.

    Like `/regenerate`, the ticket is at `processing` before this responds, so the
    workbench shows the run as soon as it reloads the ticket.
    """
    try:
        await escalation_service.record_answer(ticket_id, payload.answer_text, user.id)
        ticket = ticket_service.to_ticket(
            await ticket_service.start_processing(ticket_id, resume=False)
        )
    except LookupError:
        raise HTTPException(status_code=404, detail="No such ticket.") from None
    except IllegalTransition as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from None
    except Exception:
        logger.exception("Failed to record the department answer for ticket %s", ticket_id)
        raise HTTPException(status_code=503, detail=UNAVAILABLE) from None

    background_tasks.add_task(ticket_pipeline.process_ticket, ticket_id, "dept_response")
    return ticket


@router.post("/{ticket_id}/resolve", response_model=Ticket)
async def resolve_ticket(
    ticket_id: str,
    payload: ResolveTicketRequest,
    user: CurrentUser = Depends(get_current_user),
) -> Ticket:
    """Close a ticket, stamping `resolution_path`.

    The path is derived from the ticket's own history, not from the request —
    see `ticket_service._resolution_path_for`. This endpoint is what moves the
    escalation-rate metric, which is why it does not accept the value.
    """
    try:
        return await ticket_service.resolve_ticket(ticket_id, payload.note, user.id)
    except LookupError:
        raise HTTPException(status_code=404, detail="No such ticket.") from None
    except IllegalTransition as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from None
    except Exception:
        logger.exception("Failed to resolve ticket %s", ticket_id)
        raise HTTPException(status_code=503, detail=UNAVAILABLE) from None


@router.post("/{ticket_id}/send", response_model=Ticket)
async def send_reply(
    ticket_id: str,
    payload: SendReplyRequest,
    background_tasks: BackgroundTasks,
    user: CurrentUser = Depends(get_current_user),
) -> Ticket:
    """Email the (possibly edited) draft to the customer and resolve the ticket.

    409 for a stale or already-handled draft, an unedited holding reply, or a
    ticket that can't be resolved; 502 when the email itself fails. Once sent, the
    ticket becomes a past case in the background (the flywheel). Only a sent reply
    does: a ticket resolved by hand has nothing to learn from.
    """
    try:
        ticket = await reply_service.send_reply(
            ticket_id, payload.draft_id, payload.final_text, user.id
        )
    except LookupError:
        raise HTTPException(status_code=404, detail="No such ticket or draft.") from None
    except (IllegalTransition, DraftConflict) as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from None
    except InvalidReply as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from None
    except EmailSendError:
        raise HTTPException(status_code=502, detail=SEND_FAILED) from None
    except Exception:
        logger.exception("Failed to send the reply for ticket %s", ticket_id)
        raise HTTPException(status_code=503, detail=UNAVAILABLE) from None

    background_tasks.add_task(case_minting.mint_case, ticket_id)
    return ticket


@router.post("/{ticket_id}/discard", response_model=Ticket)
async def discard_draft(
    ticket_id: str,
    payload: DiscardDraftRequest,
    user: CurrentUser = Depends(get_current_user),
) -> Ticket:
    """Reject the latest draft with a reason. The ticket's status does not change."""
    try:
        return await reply_service.discard_draft(
            ticket_id, payload.draft_id, payload.reason, payload.note, user.id
        )
    except LookupError:
        raise HTTPException(status_code=404, detail="No such ticket or draft.") from None
    except DraftConflict as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from None
    except Exception:
        logger.exception("Failed to discard the draft for ticket %s", ticket_id)
        raise HTTPException(status_code=503, detail=UNAVAILABLE) from None


@router.post(
    "/{ticket_id}/regenerate",
    response_model=Ticket,
    status_code=202,
    dependencies=[Depends(get_current_user)],
)
async def regenerate_draft(ticket_id: str, background_tasks: BackgroundTasks) -> Ticket:
    """Run the ticket graph again in the background; a new draft version follows.

    The ticket moves to `processing` before this responds, so the workbench shows
    the run as soon as it reloads the ticket.
    """
    try:
        ticket = ticket_service.to_ticket(
            await ticket_service.start_processing(ticket_id, resume=False)
        )
    except LookupError:
        raise HTTPException(status_code=404, detail="No such ticket.") from None
    except IllegalTransition as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from None
    except Exception:
        logger.exception("Failed to regenerate the draft for ticket %s", ticket_id)
        raise HTTPException(status_code=503, detail=UNAVAILABLE) from None

    background_tasks.add_task(ticket_pipeline.process_ticket, ticket_id, "regenerate")
    return ticket
