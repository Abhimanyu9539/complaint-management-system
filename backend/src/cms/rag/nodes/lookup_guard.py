"""Lookup branch: check the answer is grounded, cited and agent-facing before it leaves the graph.
"""

import logging

from langsmith import traceable

from cms.config.settings import get_settings
from cms.guardrails.guards import run_lookup_guard
from cms.guardrails.nemo_rails import check_output
from cms.rag.context import BLOCK_SEPARATOR, build_generation_context
from cms.rag.state import GraphState

logger = logging.getLogger(__name__)


@traceable(name="lookup_guard")
async def lookup_guard(state: GraphState) -> dict:
    """The graph node: sets `grounded` and the reasons it failed.

    Same shape as `output_guard`, with the lookup guard: an answer listing past
    cases need not cite a policy. There is no retry on this branch — a failed
    answer goes to `add_caveat`.

    A check that errors counts as a failure, so the answer is caveated rather
    than passed unchecked.
    """
    settings = get_settings()
    if not settings.guardrails_enabled:
        logger.info("lookup_guard: guardrails disabled, answer not checked")
        return {"grounded": None}

    draft = state.get("draft", "")
    policy_context, case_context, offered = build_generation_context(
        state.get("policy_hits", []), state.get("case_hits", [])
    )
    context = BLOCK_SEPARATOR.join(part for part in (policy_context, case_context) if part)

    try:
        result = await run_lookup_guard(draft, offered, context)
        if result.passed and settings.nemo_rails_enabled:
            result = await check_output(state["query"], draft, context)
    except Exception:
        logger.exception("lookup_guard: a check failed; treating the answer as ungrounded")
        return {"grounded": False, "guard_reasons": [settings.guard_error_reason]}

    logger.info("lookup_guard: grounded=%s, reasons=%s", result.passed, result.reasons)
    return {"grounded": result.passed, "guard_reasons": result.reasons}
