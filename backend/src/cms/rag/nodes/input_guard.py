"""First graph node: mask sensitive data out of the complaint, and block text aimed at the assistant.
"""

import logging

from langsmith import traceable

from cms.config.settings import get_settings
from cms.guardrails.guards import run_input_guard
from cms.guardrails.nemo_rails import check_input
from cms.rag.state import GraphState

logger = logging.getLogger(__name__)


@traceable(name="input_guard")
async def input_guard(state: GraphState) -> dict:
    """The graph node: a partial `GraphState` update.

    Guardrails AI runs first (length, then masking), so the NeMo rail — an LLM
    call — only ever sees masked text. On a pass the masked text replaces
    `query`, so no later node sees what was masked.

    Fails closed: if a check errors, the complaint is blocked for manual handling
    rather than sent on unchecked.
    """
    settings = get_settings()
    if not settings.guardrails_enabled:
        logger.info("input_guard: guardrails disabled, passing the query through")
        return {"input_blocked": False}

    try:
        result = await run_input_guard(state["query"])
        if result.passed and settings.nemo_rails_enabled:
            result = await check_input(result.text)
    except Exception:
        logger.exception("input_guard: a check failed; blocking the complaint")
        return {"input_blocked": True, "guard_reasons": [settings.guard_error_reason]}

    if not result.passed:
        logger.warning("input_guard: blocked: %s", result.reasons)
        return {"input_blocked": True, "guard_reasons": result.reasons}

    logger.info("input_guard: passed")
    return {"query": result.text, "input_blocked": False, "guard_reasons": []}
