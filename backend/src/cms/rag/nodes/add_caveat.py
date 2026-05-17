"""Complaint branch: a draft that failed its checks twice goes out with a caution banner. No LLM call.
"""

import logging

from langsmith import traceable

from cms.config.settings import get_settings
from cms.rag.state import GraphState

logger = logging.getLogger(__name__)


@traceable(name="add_caveat")
async def add_caveat(state: GraphState) -> dict:
    """The graph node: prepend the caveat and the failed checks to `draft`.

    The draft is kept rather than replaced: an agent who can see the citations and
    the reasons can still use what is right in it (ai §2 — check, don't trust).
    """
    reasons = state.get("guard_reasons", [])
    logger.warning("add_caveat: draft still ungrounded after regeneration: %s", reasons)
    bullets = "\n".join(f"- {reason}" for reason in reasons)
    draft = f"{get_settings().grounding_caveat}\n{bullets}\n\n{state.get('draft', '')}"
    return {"draft": draft}
