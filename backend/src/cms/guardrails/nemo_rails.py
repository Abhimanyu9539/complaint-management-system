"""NeMo Guardrails: the LLM-judged rails, run through `check_async` only — the graph owns generation."""

import logging
from functools import lru_cache
from pathlib import Path

from nemoguardrails import LLMRails, RailsConfig
from nemoguardrails.rails.llm.options import RailsResult, RailStatus, RailType

from cms.config.settings import get_settings
from cms.schemas.guardrails import GuardResult

logger = logging.getLogger(__name__)

PROMPTS_FILE = Path(__file__).parent / "nemo" / "prompts.yml"


@lru_cache
def get_rails() -> LLMRails:
    """The rails, built once: the cheap model over OpenRouter and three self-check prompts."""
    settings = get_settings()
    config = {
        "models": [
            {
                "type": "main",
                "engine": "openai",
                "model": settings.openrouter_model_cheap,
                "parameters": {
                    "base_url": settings.openrouter_base_url,
                    "api_key": settings.open_router_api_key,
                    "timeout": settings.openrouter_timeout_seconds,
                },
            }
        ],
        "rails": {
            "input": {"flows": ["self check input"]},
            "output": {"flows": ["self check facts", "self check output"]},
        },
    }
    try:
        prompts = PROMPTS_FILE.read_text(encoding="utf-8")
        return LLMRails(RailsConfig.from_content(yaml_content=prompts, config=config))
    except Exception:
        logger.exception("Failed to build the NeMo rails from %s", PROMPTS_FILE)
        raise


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
        result = await get_rails().check_async(
            [{"role": "user", "content": query}], rail_types=[RailType.INPUT]
        )
    except Exception:
        logger.exception("nemo input check failed")
        raise
    return _to_guard_result(result, query, "nemo input check")


async def check_output(query: str, draft: str, context: str) -> GuardResult:
    """Fact-check `draft` against `context`, and check it is written to the agent."""
    messages = [
        # `check_facts` switches the fact-check rail on; without it that rail is skipped.
        {"role": "context", "content": {"relevant_chunks": context, "check_facts": True}},
        {"role": "user", "content": query},
        {"role": "assistant", "content": draft},
    ]
    try:
        result = await get_rails().check_async(messages, rail_types=[RailType.OUTPUT])
    except Exception:
        logger.exception("nemo output check failed")
        raise
    return _to_guard_result(result, draft, "nemo output check")
