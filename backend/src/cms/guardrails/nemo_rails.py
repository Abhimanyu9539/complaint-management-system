"""NeMo Guardrails: the LLM-judged rails, run through `check_async` only — the graph owns generation."""

import logging
from functools import lru_cache
from pathlib import Path

from nemoguardrails import LLMRails, RailsConfig
from nemoguardrails.rails.llm.options import RailsResult, RailStatus, RailType

from cms.config.settings import get_settings
from cms.guardrails.fact_check import find_unsupported_claims
from cms.schemas.guardrails import GuardResult

logger = logging.getLogger(__name__)

PROMPTS_FILE = Path(__file__).parent / "nemo" / "prompts.yml"
FACTS_RAIL = "self check facts"


def _build_rails(model: str, rails: dict) -> LLMRails:
    """One `LLMRails` over OpenRouter with the shared self-check prompts. NeMo takes one model per instance."""
    settings = get_settings()
    config = {
        "models": [
            {
                "type": "main",
                "engine": "openai",
                "model": model,
                "parameters": {
                    "base_url": settings.openrouter_base_url,
                    "api_key": settings.open_router_api_key,
                    "timeout": settings.openrouter_timeout_seconds,
                },
            }
        ],
        "rails": rails,
    }
    try:
        prompts = PROMPTS_FILE.read_text(encoding="utf-8")
        return LLMRails(RailsConfig.from_content(yaml_content=prompts, config=config))
    except Exception:
        logger.exception("Failed to build the NeMo rails (model=%s) from %s", model, PROMPTS_FILE)
        raise


@lru_cache
def get_input_rails() -> LLMRails:
    """The input rail on the cheap model: spotting instructions aimed at the assistant is an easy call."""
    return _build_rails(get_settings().openrouter_model_cheap, {"input": {"flows": ["self check input"]}})


@lru_cache
def get_output_rails() -> LLMRails:
    """The output rails on the judge model: the cheap one missed invented remedies (see `guard_judge_model`)."""
    return _build_rails(
        get_settings().guard_judge_model,
        {"output": {"flows": [FACTS_RAIL, "self check output"]}},
    )


def _to_guard_result(result: RailsResult, text: str, check: str) -> GuardResult:
    if result.status == RailStatus.BLOCKED:
        logger.warning("%s: blocked by '%s'", check, result.rail)
        feedback = get_settings().rail_feedback.get(result.rail, f"Blocked by '{result.rail}'.")
        return GuardResult(passed=False, text=text, reasons=[feedback])
    logger.info("%s: %s", check, result.status.value)
    return GuardResult(passed=True, text=text)


async def check_input(query: str) -> GuardResult:
    """Block a complaint that tries to instruct the assistant, or is abuse with no complaint."""
    try:
        result = await get_input_rails().check_async(
            [{"role": "user", "content": query}], rail_types=[RailType.INPUT]
        )
    except Exception:
        logger.exception("nemo input check failed")
        raise
    return _to_guard_result(result, query, "nemo input check")


async def check_output(query: str, draft: str, context: str) -> GuardResult:
    """Fact-check `draft` against `context`, and check it is written to the agent.

    A fact-check block is followed by the claim finder, so the reasons name the
    claims that failed. If it finds none or errors, the draft stays blocked with
    the generic reason — a disagreement never lets a draft through.
    """
    messages = [
        # `check_facts` switches the fact-check rail on; without it that rail is skipped.
        {"role": "context", "content": {"relevant_chunks": context, "check_facts": True}},
        {"role": "user", "content": query},
        {"role": "assistant", "content": draft},
    ]
    try:
        result = await get_output_rails().check_async(messages, rail_types=[RailType.OUTPUT])
    except Exception:
        logger.exception("nemo output check failed")
        raise

    guard_result = _to_guard_result(result, draft, "nemo output check")
    if result.status != RailStatus.BLOCKED or result.rail != FACTS_RAIL:
        return guard_result

    try:
        claims = await find_unsupported_claims(draft, context)
    except Exception:
        logger.exception("nemo output check: claim finder failed, keeping the generic reason")
        return guard_result

    if not claims:
        logger.warning("nemo output check: fact check blocked but the claim finder found no claim")
        return guard_result

    reasons = [f'"{claim.claim}": {claim.reason}' for claim in claims]
    return GuardResult(passed=False, text=draft, reasons=reasons)
