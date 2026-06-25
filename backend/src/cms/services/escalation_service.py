"""Escalate a ticket to a department (Path B): draft the question, email it, record the answer.

Status changes stay in `ticket_service`; this module does the work around them.
"""

import logging

from langsmith import traceable

from cms.config.settings import get_settings
from cms.db.repositories import dept_responses, drafts, tickets
from cms.guardrails.guards import run_input_guard
from cms.llm.chat.openrouter_chat import get_chat_model
from cms.llm.prompts.registry import load_prompt
from cms.rag.nodes.classify_ticket import join_complaint
from cms.schemas.tickets import DeptQuestion, Ticket
from cms.services import ticket_service
from cms.services.email_sender import send_email
from cms.services.reply_service import strip_markers

logger = logging.getLogger(__name__)

PROMPT_NAME = "dept_question"


def _normalise(text: str) -> str:
    return " ".join(text.split())


async def _masked_complaint(ticket: dict) -> str:
    """The complaint with sensitive data masked, as the ticket graph sees it. Never the raw text."""
    complaint = join_complaint(ticket["subject"], ticket.get("body"))
    if not get_settings().guardrails_enabled:
        return complaint

    result = await run_input_guard(complaint)
    if not result.passed:
        raise RuntimeError(f"The complaint did not pass the input guard: {result.reasons}")
    return result.text


@traceable(name="dept_question")
async def _write_question(
    department: dict, complaint: str, current_draft: str, review_reasons: list[str]
) -> str:
    settings = get_settings()
    prompt = load_prompt(PROMPT_NAME, settings.dept_question_prompt_version)
    chain = prompt | get_chat_model(settings.openrouter_model_cheap)
    message = await chain.ainvoke(
        {
            "department": f"{department['name']}: {department['description']}",
            "complaint": complaint,
            "current_draft": current_draft,
            "review_reasons": "\n".join(f"- {reason}" for reason in review_reasons),
        }
    )
    return message.content.strip()


async def draft_question(ticket_id: str, department_id: str) -> DeptQuestion:
    """Draft a question for the department and save it as a `dept_question` draft. Nothing is sent."""
    ticket = await tickets.fetch_ticket(ticket_id)
    ticket_service.assert_transition(ticket["status"], "escalated")
    department = await ticket_service.get_department(department_id)

    reply = await drafts.fetch_latest_draft(ticket_id)
    current_draft = strip_markers(reply["draft_text"]) if reply else ""
    complaint = await _masked_complaint(ticket)

    try:
        text = await _write_question(
            department, complaint, current_draft, ticket.get("review_reasons") or []
        )
    except Exception:
        logger.exception("Ticket %s: drafting the question for %s failed", ticket_id, department_id)
        raise
    if not text:
        raise RuntimeError("The model returned an empty question.")

    settings = get_settings()
    previous = await drafts.fetch_latest_draft(ticket_id, drafts.DEPT_QUESTION)
    saved = await drafts.insert_draft(
        {
            "ticket_id": ticket_id,
            "version": previous["version"] + 1 if previous else 1,
            "kind": drafts.DEPT_QUESTION,
            "draft_text": text,
            "model": settings.openrouter_model_cheap,
            "prompt_version": settings.dept_question_prompt_version,
        }
    )
    logger.info("Ticket %s: question for %s drafted (v%d)", ticket_id, department_id, saved["version"])
    return DeptQuestion(draft_id=saved["id"], department_id=department_id, text=text)


async def _question_edited(ticket_id: str, draft_id: str, question: str) -> bool | None:
    """Whether the agent changed the drafted question. None if that draft is not this ticket's question."""
    try:
        draft = await drafts.fetch_draft(draft_id)
    except LookupError:
        logger.warning("Ticket %s: question draft %s not found", ticket_id, draft_id)
        return None
    if draft["ticket_id"] != ticket_id or draft["kind"] != drafts.DEPT_QUESTION:
        return None
    return _normalise(draft["draft_text"]) != _normalise(question)


async def escalate(
    ticket_id: str, department_id: str, question: str, question_draft_id: str | None = None
) -> Ticket:
    """Email the question to the department, then mark the ticket escalated.

    Every read happens before the email, and the email before any write: if the
    send fails (`EmailSendError`), nothing has changed and the agent can retry.
    """
    ticket = await tickets.fetch_ticket(ticket_id)
    ticket_service.assert_transition(ticket["status"], "escalated")
    department = await ticket_service.get_department(department_id)

    question = question.strip()
    edited = await _question_edited(ticket_id, question_draft_id, question) if question_draft_id else None

    settings = get_settings()
    subject = settings.dept_question_subject_template.format(
        ticket_no=ticket["ticket_no"], subject=ticket["subject"]
    )
    body = settings.dept_question_body_template.format(
        question=question,
        ticket_no=ticket["ticket_no"],
        subject=ticket["subject"],
        body=ticket.get("body") or "",
    )
    message_id = await send_email(department["mailbox"], subject, body)

    try:
        return await ticket_service.escalate_ticket(
            ticket_id,
            department_id,
            question,
            email={
                "to": department["mailbox"],
                "message_id": message_id,
                "question_draft_id": question_draft_id,
                "edited": edited,
            },
        )
    except Exception:
        logger.exception(
            "Ticket %s: the question was emailed to %s but the ticket was not escalated",
            ticket_id,
            department_id,
        )
        raise


async def record_answer(ticket_id: str, answer_text: str) -> Ticket:
    """Save the department's answer and move the ticket to `dept_responded`.

    The transition is checked before the insert, so a refused request leaves no row.
    The caller then runs the ticket graph again to redraft from the answer.
    """
    ticket = await tickets.fetch_ticket(ticket_id)
    ticket_service.assert_transition(ticket["status"], "dept_responded")

    response = await dept_responses.insert_response(
        {
            "ticket_id": ticket_id,
            "department_id": ticket["escalated_dept"],
            "answer_text": answer_text.strip(),
        }
    )
    return await ticket_service.mark_dept_responded(ticket_id, response)
