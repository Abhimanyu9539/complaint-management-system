"""Blocked-input branch: tell the agent to handle this complaint manually. No LLM call.
"""

import logging

from langsmith import traceable

from cms.config.settings import get_settings
from cms.rag.state import GraphState

logger = logging.getLogger(__name__)


@traceable(name="blocked_input")
async def blocked_input(state: GraphState) -> dict:
    """The graph node: writes the fixed note into `draft`, the slot every branch fills."""
    logger.info("blocked_input: %s", state.get("guard_reasons", []))
    return {"draft": get_settings().blocked_input_message, "citations": []}
