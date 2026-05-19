"""Complaint branch: check the draft is grounded, cited and agent-facing before it leaves the graph.
"""

import logging

from langsmith import traceable

from cms.config.settings import get_settings
from cms.guardrails.guards import run_output_guard
from cms.guardrails.nemo_rails import check_output
from cms.rag.context import BLOCK_SEPARATOR, build_generation_context
from cms.rag.state import GraphState

logger = logging.getLogger(__name__)


@traceable(name="output_guard")
async def output_guard(state: GraphState) -> dict:
    """The graph node: sets `grounded` and the reasons it failed.

    The context is rebuilt with `build_generation_context`, which is pure, so the
    checks see exactly what `generate` was shown. The NeMo rails (LLM calls) run
    only when the deterministic checks pass — a failed draft is regenerated anyway.

    A check that errors counts as a failure, so the draft is retried or caveated
    rather than passed unchecked.
    """
    settings = get_settings()
    if not settings.guardrails_enabled:
        logger.info("output_guard: guardrails disabled, draft not checked")
        return {"grounded": None}

    draft = state.get("draft", "")
    policy_context, case_context, offered = build_generation_context(
        state.get("policy_hits", []), state.get("case_hits", [])
    )
    context = BLOCK_SEPARATOR.join(part for part in (policy_context, case_context) if part)

    try:
        result = await run_output_guard(draft, offered, context)
        if result.passed and settings.nemo_rails_enabled:
            result = await check_output(state["query"], draft, context)
    except Exception:
        logger.exception("output_guard: a check failed; treating the draft as ungrounded")
        return {"grounded": False, "guard_reasons": [settings.guard_error_reason]}

    logger.info("output_guard: grounded=%s, reasons=%s", result.passed, result.reasons)
    return {"grounded": result.passed, "guard_reasons": result.reasons}
