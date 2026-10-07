"""Ticket intake and lifecycle. Every route needs a signed-in agent except `POST /tickets`, the customer form.

Errors are mapped to status codes in `cms.api.errors`.
"""

import logging
from typing import Literal

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query

from cms.api.deps import get_current_user
from cms.api.errors import EXPECTED_ERRORS, ErrorRoute
from cms.config.settings import get_settings
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

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/tickets", tags=["tickets"], route_class=ErrorRoute)


@router.post("", response_model=TicketCreated, status_code=201)
async def create_ticket(
    payload: CreateTicketRequest, background_tasks: BackgroundTasks
) -> TicketCreated:
    """Open a ticket from the customer form; the ticket graph drafts it in the background.

    ⚠ Unauthenticated and not rate limited: put a limiter in front of it before deploying publicly.
    """
    try:
        created = await ticket_service.create_ticket(
            subject=payload.subject.strip(),
            body=payload.body.strip(),
            customer_email=payload.customer_email.strip().lower(),
            severity=payload.severity,
        )
    except Exception:
        # The customer gets their own message: their complaint is still in the form.
        logger.exception("Failed to create a ticket")
        raise HTTPException(
            status_code=503, detail=get_settings().ticket_create_failed_message
        ) from None

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
    return await ticket_service.build_ticket_page(
        status=status, severity=severity, search=search, limit=limit, offset=offset
    )


@router.get("/{ticket_id}", response_model=TicketDetail, dependencies=[Depends(get_current_user)])
async def get_ticket(ticket_id: str) -> TicketDetail:
    """One ticket plus its audit trail and latest draft."""
    return await ticket_service.get_ticket(ticket_id)


@router.post(
    "/{ticket_id}/dept-question", response_model=DeptQuestion, dependencies=[Depends(get_current_user)]
)
async def draft_dept_question(ticket_id: str, payload: DraftDeptQuestionRequest) -> DeptQuestion:
    """Draft the question to send the department. Nothing is sent or changed on the ticket."""
    try:
        return await escalation_service.draft_question(ticket_id, payload.department_id)
    except EXPECTED_ERRORS:
        raise
    except Exception:
        # Usually the model call; the agent can write the question by hand.
        logger.exception("Failed to draft the department question for ticket %s", ticket_id)
        raise HTTPException(
            status_code=503, detail=get_settings().dept_question_failed_message
        ) from None


@router.post("/{ticket_id}/escalate", response_model=Ticket)
async def escalate_ticket(
    ticket_id: str,
    payload: EscalateTicketRequest,
    user: CurrentUser = Depends(get_current_user),
) -> Ticket:
    """Email the question to a department and hand the ticket over (Path B)."""
    return await escalation_service.escalate(
        ticket_id, payload.department_id, payload.note, payload.question_draft_id, user.id
    )


@router.post("/{ticket_id}/dept-response", response_model=Ticket, status_code=202)
async def record_dept_response(
    ticket_id: str,
    payload: DeptResponseRequest,
    background_tasks: BackgroundTasks,
    user: CurrentUser = Depends(get_current_user),
) -> Ticket:
    """Save the department's answer; the ticket graph then redrafts from it in the background."""
    await escalation_service.record_answer(ticket_id, payload.answer_text, user.id)
    ticket = ticket_service.to_ticket(
        await ticket_service.start_processing(ticket_id, resume=False)
    )
    background_tasks.add_task(ticket_pipeline.process_ticket, ticket_id, "dept_response")
    return ticket


@router.post("/{ticket_id}/resolve", response_model=Ticket)
async def resolve_ticket(
    ticket_id: str,
    payload: ResolveTicketRequest,
    user: CurrentUser = Depends(get_current_user),
) -> Ticket:
    """Close a ticket. `resolution_path` comes from the ticket's history, never the request."""
    return await ticket_service.resolve_ticket(ticket_id, payload.note, user.id)


@router.post("/{ticket_id}/send", response_model=Ticket)
async def send_reply(
    ticket_id: str,
    payload: SendReplyRequest,
    background_tasks: BackgroundTasks,
    user: CurrentUser = Depends(get_current_user),
) -> Ticket:
    """Email the (possibly edited) draft to the customer and resolve the ticket.

    Once sent, the ticket becomes a past case in the background (the flywheel).
    """
    ticket = await reply_service.send_reply(
        ticket_id, payload.draft_id, payload.final_text, user.id
    )
    background_tasks.add_task(case_minting.mint_case, ticket_id)
    return ticket


@router.post("/{ticket_id}/discard", response_model=Ticket)
async def discard_draft(
    ticket_id: str,
    payload: DiscardDraftRequest,
    user: CurrentUser = Depends(get_current_user),
) -> Ticket:
    """Reject the latest draft with a reason. The ticket's status does not change."""
    return await reply_service.discard_draft(
        ticket_id, payload.draft_id, payload.reason, payload.note, user.id
    )


@router.post(
    "/{ticket_id}/regenerate",
    response_model=Ticket,
    status_code=202,
    dependencies=[Depends(get_current_user)],
)
async def regenerate_draft(ticket_id: str, background_tasks: BackgroundTasks) -> Ticket:
    """Run the ticket graph again in the background; a new draft version follows."""
    ticket = ticket_service.to_ticket(
        await ticket_service.start_processing(ticket_id, resume=False)
    )
    background_tasks.add_task(ticket_pipeline.process_ticket, ticket_id, "regenerate")
    return ticket
