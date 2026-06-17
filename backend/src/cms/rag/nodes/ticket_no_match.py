"""Ticket-graph node: no policy matched, so the draft is a holding reply. No LLM call.
"""

import logging

from langsmith import traceable

from cms.config.settings import get_settings
from cms.rag.ticket_state import TicketState

logger = logging.getLogger(__name__)


@traceable(name="ticket_no_match")
async def ticket_no_match(state: TicketState) -> dict:
    """The ticket-graph node: acknowledge the complaint with its reference and promise nothing."""
    logger.info("ticket_no_match: no policy matched ticket %s, writing the holding reply", state["ticket_id"])
    ticket_no = state.get("ticket_no", "")
    return {"draft": get_settings().holding_reply_message.format(ticket_no=ticket_no), "citations": []}
