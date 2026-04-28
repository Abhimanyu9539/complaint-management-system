"""Smalltalk branch: greet, or say what this assistant is for. No retrieval.
"""

import logging

from langsmith import traceable

from cms.config.settings import get_settings
from cms.llm.chat.openrouter_chat import get_chat_model
from cms.llm.prompts.registry import load_prompt
from cms.rag.state import GraphState

logger = logging.getLogger(__name__)


async def smalltalk_core(query: str) -> str:
    """A short conversational reply to `query`.
    """
    settings = get_settings()
    prompt = load_prompt("smalltalk")
    chain = prompt | get_chat_model(settings.openrouter_model_cheap)

    try:
        message = await chain.ainvoke({"query": query})
    except Exception:
        logger.exception("smalltalk failed for query %r", query)
        raise

    reply = message.content
    logger.info("smalltalk: replied to %r", query)
    return reply


@traceable(name="smalltalk")
async def smalltalk(state: GraphState) -> dict:
    """The graph node: a partial `GraphState` update."""
    return {"draft": await smalltalk_core(state["query"])}
