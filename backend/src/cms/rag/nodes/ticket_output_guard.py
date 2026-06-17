"""Ticket-graph node: check the customer reply is grounded, cited and fit to send.
"""

import logging

from langsmith import traceable

from cms.config.settings import get_settings
from cms.guardrails.guards import run_output_guard
from cms.guardrails.nemo_rails import check_customer_reply
from cms.rag.context import BLOCK_SEPARATOR, build_generation_context
from cms.rag.ticket_state import TicketState

logger = logging.getLogger(__name__)


@traceable(name="ticket_output_guard")
async def ticket_output_guard(state: TicketState) -> dict:
    """The ticket-graph node: sets `grounded` and the reasons it failed.

    Like the chat's `output_guard`, with two differences. The number check also
    sees the complaint, because a reply may repeat a figure the customer gave
    ("dead after 3 months"). The NeMo fact check does not, so a remedy the
    customer demands never counts as evidence for it.

    A check that errors counts as a failure, so the draft is retried or saved
    as ungrounded rather than passed unchecked.
    """
    settings = get_settings()
    if not settings.guardrails_enabled:
        logger.info("ticket_output_guard: guardrails disabled, draft not checked")
        return {"grounded": None}

    draft = state.get("draft", "")
    policy_context, case_context, offered = build_generation_context(
        state.get("policy_hits", []), state.get("case_hits", [])
    )
    context = BLOCK_SEPARATOR.join(part for part in (policy_context, case_context) if part)
    context_with_complaint = BLOCK_SEPARATOR.join((context, state["query"]))

    try:
        result = await run_output_guard(draft, offered, context_with_complaint)
        if result.passed and settings.nemo_rails_enabled:
            result = await check_customer_reply(state["query"], draft, context)
    except Exception:
        logger.exception("ticket_output_guard: a check failed; treating the draft as ungrounded")
        return {"grounded": False, "guard_reasons": [settings.guard_error_reason]}

    logger.info("ticket_output_guard: grounded=%s, reasons=%s", result.passed, result.reasons)
    return {"grounded": result.passed, "guard_reasons": result.reasons}
