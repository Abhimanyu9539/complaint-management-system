"""The flywheel: a ticket whose reply was sent becomes a past case the drafter can cite.

Runs as a background task after `/send`, so it never raises: a failure is logged
and written as a `failed` event with `stage: mint_case`. The reply has already
gone out; only the case is missing.
"""

import logging

from guardrails import OnFailAction
from guardrails.validator_base import FailResult
from langsmith import traceable

from cms.config.settings import get_settings
from cms.db.repositories import (
    cases,
    dept_responses,
    draft_feedback,
    drafts,
    ticket_events,
    tickets,
)
from cms.guardrails.guards import scrub_case_text
from cms.guardrails.validators import NumbersInSources
from cms.ingestion.extract.cases_extractor import build_case_text
from cms.ingestion.pipeline import ingest_case
from cms.llm.chat.openrouter_chat import get_chat_model
from cms.llm.prompts.registry import load_prompt
from cms.rag.nodes.classify_ticket import join_complaint

logger = logging.getLogger(__name__)

PROMPT_NAME = "case_resolution"
FAILED_STAGE = "mint_case"

# What an agent did with a draft that means it reached the customer.
SENT_ACTIONS = ("accepted", "edited")


def mask_entities(text: str, entities: dict | None) -> str:
    """Replace the ticket's own order and invoice numbers with placeholders (privacy §6)."""
    for key, mask in get_settings().case_entity_masks.items():
        value = (entities or {}).get(key)
        if value:
            text = text.replace(str(value), mask)
    return text


def has_unsupported_figures(summary: str, sources: str) -> bool:
    """Whether the summary states an amount, period or percentage the sources don't."""
    result = NumbersInSources(on_fail=OnFailAction.NOOP).validate(summary, {"context": sources})
    return isinstance(result, FailResult)


async def _sent_reply(ticket_id: str) -> str | None:
    """The text emailed for the latest reply draft, or None if that draft was not sent."""
    draft = await drafts.fetch_latest_draft(ticket_id)
    if not draft:
        return None
    feedback = await draft_feedback.fetch_feedback(draft["id"])
    if not feedback or feedback["action"] not in SENT_ACTIONS:
        return None
    return feedback.get("final_text") or None


async def _guidance_text(ticket_id: str) -> str:
    """Every department answer on the ticket, oldest first, as one text."""
    responses = await dept_responses.list_responses(ticket_id)
    return "\n\n".join(response["answer_text"] for response in reversed(responses))


@traceable(name="case_resolution")
async def _summarise_resolution(complaint: str, guidance: str, reply: str) -> str:
    settings = get_settings()
    prompt = load_prompt(PROMPT_NAME, settings.case_resolution_prompt_version)
    chain = prompt | get_chat_model(settings.openrouter_model_cheap)
    message = await chain.ainvoke({"complaint": complaint, "guidance": guidance, "reply": reply})
    return message.content.strip()


async def _resolution_text(complaint: str, guidance: str, reply: str) -> tuple[str, bool]:
    """`(resolution, fallback)`: the scrubbed summary, or the reply when the summary can't be trusted."""
    try:
        summary = await _summarise_resolution(complaint, guidance, reply)
    except Exception:
        logger.exception("Case resolution summary failed; using the sent reply")
        return reply, True

    if not summary:
        logger.warning("Case resolution summary was empty; using the sent reply")
        return reply, True
    if has_unsupported_figures(summary, f"{reply}\n\n{guidance}"):
        logger.warning("Case resolution summary states a figure the sources don't; using the sent reply")
        return reply, True
    return await scrub_case_text(summary), False


async def _mint(ticket_id: str) -> None:
    settings = get_settings()
    ticket = await tickets.fetch_ticket(ticket_id)
    if ticket["status"] != "resolved":
        logger.info("Ticket %s is %s, not resolved: no case minted", ticket_id, ticket["status"])
        return

    reply = await _sent_reply(ticket_id)
    if not reply:
        logger.info("Ticket %s has no sent reply: no case minted", ticket_id)
        return

    department = ticket.get("escalated_dept") or ticket.get("predicted_dept")
    if not department:
        logger.warning("Ticket %s has no department: no case minted", ticket_id)
        return

    # Our own identifiers first, then Presidio; nothing unscrubbed is stored.
    entities = ticket.get("entities") or {}
    complaint = await scrub_case_text(
        mask_entities(join_complaint(ticket["subject"], ticket.get("body")), entities)
    )
    guidance = await scrub_case_text(mask_entities(await _guidance_text(ticket_id), entities))
    reply = await scrub_case_text(mask_entities(reply, entities))
    resolution, fallback = await _resolution_text(complaint, guidance, reply)

    category = ticket.get("category") or "other"
    row = {
        "ticket_id": ticket_id,
        "title": settings.flywheel_case_title_template.format(
            ticket_no=ticket["ticket_no"], department=department, category=category
        ),
        "department_id": department,
        "category": category,
        "complaint_text": complaint,
        "dept_guidance": guidance or None,
        "resolution_text": resolution,
        "resolution_path": ticket.get("resolution_path"),
        "source": "flywheel",
    }
    case_id = await cases.upsert_flywheel_case(row)
    # Its own ingestion job, so a failed run shows on the admin ingestion page and can be retried.
    await ingest_case(case_id, build_case_text(row))

    await ticket_events.append_event(
        ticket_id,
        "case_minted",
        {
            "case_id": case_id,
            "fallback": fallback,
            "model": settings.openrouter_model_cheap,
            "prompt_version": settings.case_resolution_prompt_version,
        },
    )
    logger.info("Ticket %s minted case %s (fallback=%s)", ticket_id, case_id, fallback)


async def mint_case(ticket_id: str) -> None:
    """Add the ticket to the case corpus, or refresh its case. Never raises."""
    if not get_settings().flywheel_enabled:
        logger.info("Ticket %s: the flywheel is off, no case minted", ticket_id)
        return

    try:
        await _mint(ticket_id)
    except Exception as exc:
        logger.exception("Ticket %s: minting the case failed", ticket_id)
        await ticket_events.append_event(
            ticket_id, "failed", {"stage": FAILED_STAGE, "error": f"{type(exc).__name__}: {exc}"}
        )
