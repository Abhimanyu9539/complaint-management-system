"""Before a new email opens a ticket: is a customer writing, or is it automated mail?"""

import logging

from langsmith import traceable

from cms.config.settings import get_settings
from cms.guardrails.guards import run_input_guard
from cms.llm.chat.openrouter_chat import get_chat_model
from cms.llm.prompts.registry import load_prompt
from cms.observability.usage import UsageCollector
from cms.schemas.emails import EmailScreen

logger = logging.getLogger(__name__)

PROMPT_NAME = "email_screen"


@traceable(name="email_screen")
async def _judge(subject: str, body: str) -> EmailScreen:
    settings = get_settings()
    prompt = load_prompt(PROMPT_NAME, settings.email_screen_prompt_version)
    model = get_chat_model(settings.openrouter_model_cheap).with_structured_output(EmailScreen)
    chain = prompt | model
    return await chain.ainvoke(
        {"subject": subject, "body": body},
        # Counted in the metrics only; there is no run row to save it on.
        config={"callbacks": [UsageCollector(default_node=PROMPT_NAME)]},
    )


async def _masked(text: str) -> str | None:
    """`text` with sensitive data masked, or None if the input guard refused it."""
    if not get_settings().guardrails_enabled:
        return text
    result = await run_input_guard(text)
    return result.text if result.passed else None


async def screen_email(subject: str, text: str) -> EmailScreen | None:
    """The model's verdict on a new email, or None when it could not be checked.

    None opens the ticket anyway: an extra ticket is safer than a lost complaint.
    """
    settings = get_settings()
    if not settings.email_screen_enabled:
        return None

    try:
        body = await _masked(text.strip()[: settings.email_screen_max_chars])
        if body is None:
            logger.info("Email screen skipped: the input guard refused the body")
            return None
        verdict = await _judge(subject.strip(), body)
    except Exception:
        logger.exception("Email screen failed; opening the ticket anyway")
        return None

    logger.info("Email screen: %s (%s)", verdict.kind, verdict.reason)
    return verdict
