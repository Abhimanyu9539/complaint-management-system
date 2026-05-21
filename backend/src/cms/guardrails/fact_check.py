"""Claim finder: when NeMo's fact check blocks a draft, name the claims that failed."""

import logging

from cms.config.settings import get_settings
from cms.llm.chat.openrouter_chat import get_chat_model
from cms.llm.prompts.registry import load_prompt
from cms.schemas.guardrails import FactCheckFindings, UnsupportedClaim

logger = logging.getLogger(__name__)


async def find_unsupported_claims(draft: str, context: str) -> list[UnsupportedClaim]:
    """The material claims in `draft` that `context` does not support, at most `fact_check_max_claims`.

    NeMo's fact check only answers yes or no. This runs after a "no", so the retry
    and the caution banner can say which claims to fix.
    """
    settings = get_settings()
    prompt = load_prompt("fact_check_claims", settings.fact_check_prompt_version)
    model = get_chat_model(settings.openrouter_model_cheap).with_structured_output(FactCheckFindings)
    chain = prompt | model

    try:
        findings = await chain.ainvoke({"context": context, "draft": draft})
    except Exception:
        logger.exception("fact check claim finder failed")
        raise

    claims = findings.unsupported_claims[: settings.fact_check_max_claims]
    logger.info(
        "fact check claim finder: %d unsupported claim(s), keeping %d",
        len(findings.unsupported_claims),
        len(claims),
    )
    return claims
