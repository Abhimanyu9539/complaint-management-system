"""Lookup branch: an answer that failed its checks goes out with a caution banner. No LLM call.
"""

import logging

from langsmith import traceable

from cms.config.settings import get_settings
from cms.rag.state import GraphState

logger = logging.getLogger(__name__)


@traceable(name="lookup_caveat")
async def lookup_caveat(state: GraphState) -> dict:
    """The graph node: prepend the caveat and the failed checks to `draft`.

    The answer is kept rather than replaced, as on the complaint branch: the agent
    can check each cited source against the reasons and keep what holds.
    """
    reasons = state.get("guard_reasons", [])
    logger.warning("lookup_caveat: answer failed its checks: %s", reasons)
    bullets = "\n".join(f"- {reason}" for reason in reasons)
    draft = f"{get_settings().grounding_caveat}\n{bullets}\n\n{state.get('draft', '')}"
    return {"draft": draft}
