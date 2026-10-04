"""Last graph node: fold the oldest turns into the running summary once they no longer fit.
"""

import logging

from langsmith import traceable

from cms.config.settings import get_settings
from cms.llm.chat.openrouter_chat import get_chat_model
from cms.llm.prompts.registry import load_prompt
from cms.rag.memory import format_turns, turns_to_fold
from cms.rag.state import GraphState

logger = logging.getLogger(__name__)


async def compact_history_core(summary: str, turns: str) -> str:
    """`summary` with `turns` merged in, one section per complaint."""
    settings = get_settings()
    prompt = load_prompt("compact_history", settings.compact_history_prompt_version)
    chain = prompt | get_chat_model(settings.openrouter_model_cheap)

    try:
        message = await chain.ainvoke(
            {
                "summary": summary or "(none yet)",
                "turns": turns,
                "max_words": settings.memory_summary_max_words,
            }
        )
    except Exception:
        logger.exception("compact_history failed folding %d char(s) of turns", len(turns))
        raise

    return message.content.strip() if isinstance(message.content, str) else ""


@traceable(name="compact_history")
async def compact_history(state: GraphState) -> dict:
    """The graph node: a new summary and how far it reaches, or nothing while the turns still fit.

    Never raises. The answer has already streamed when this runs, and an error
    here would end the run before the turn is checkpointed — so a failed fold
    keeps the old summary, and the next turn tries again.
    """
    fold = turns_to_fold(state)
    if not fold:
        return {}

    try:
        summary = await compact_history_core(state.get("history_summary", ""), format_turns(fold))
    except Exception:
        logger.warning("compact_history: fold failed, keeping the old summary")
        return {}

    if not summary:
        logger.warning("compact_history: the model returned an empty summary, keeping the old one")
        return {}

    summarized_count = state.get("summarized_count", 0) + len(fold)
    logger.info(
        "compact_history: folded %d message(s); summary covers %d, %d chars",
        len(fold),
        summarized_count,
        len(summary),
    )
    return {"history_summary": summary, "summarized_count": summarized_count}
