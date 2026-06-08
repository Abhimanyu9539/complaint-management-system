"""Lookup branch: nothing relevant in the corpus the agent asked about — say so plainly. No LLM call.
"""

import logging

from langsmith import traceable

from cms.config.settings import get_settings
from cms.rag.state import GraphState

logger = logging.getLogger(__name__)


@traceable(name="lookup_no_match")
async def lookup_no_match(state: GraphState) -> dict:
    """The graph node: writes the fixed lookup message into `draft`, the slot every branch fills."""
    logger.info("lookup_no_match: nothing relevant for lookup %r", state["query"])
    return {"draft": get_settings().lookup_no_match_message, "citations": []}
