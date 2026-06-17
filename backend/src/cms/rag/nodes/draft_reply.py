"""Ticket-graph node: write the reply to the customer from the retrieved policies and cases.
"""

import logging

from langsmith import traceable

from cms.config.settings import get_settings
from cms.rag.nodes.generate import generate_core
from cms.rag.ticket_state import TicketState

logger = logging.getLogger(__name__)

PROMPT_NAME = "customer_reply"


@traceable(name="draft_reply")
async def draft_reply(state: TicketState) -> dict:
    """The ticket-graph node: a partial `TicketState` update.

    Same retry contract as the chat's `generate`: a second run gets the failed
    draft and the guard's reasons, and sets `regenerated`, which caps the loop.
    """
    retry = state.get("grounded") is False
    feedback = state.get("guard_reasons") if retry else None
    previous_draft = state.get("draft") if retry else None
    if retry:
        logger.info("draft_reply: revising the failed draft with %d guard reason(s)", len(feedback or []))

    draft, citations = await generate_core(
        state["query"],
        state.get("policy_hits", []),
        state.get("case_hits", []),
        feedback=feedback,
        previous_draft=previous_draft,
        prompt_name=PROMPT_NAME,
        prompt_version=get_settings().customer_reply_prompt_version,
    )
    update = {"draft": draft, "citations": citations}
    if retry:
        update["regenerated"] = True
    return update
