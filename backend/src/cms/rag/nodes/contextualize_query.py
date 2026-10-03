"""Rewrite a follow-up into a standalone question, so analysis and retrieval see the conversation.
"""

import logging

from langsmith import traceable

from cms.config.settings import get_settings
from cms.llm.chat.openrouter_chat import get_chat_model
from cms.llm.prompts.registry import load_prompt
from cms.rag.memory import format_conversation
from cms.rag.state import GraphState

logger = logging.getLogger(__name__)


async def contextualize_query_core(query: str, conversation: str) -> str:
    """`query` rewritten to stand on its own, using `conversation`. Falls back to `query` if empty."""
    settings = get_settings()
    prompt = load_prompt("contextualize_query", settings.contextualize_query_prompt_version)
    chain = prompt | get_chat_model(settings.openrouter_model_cheap)

    try:
        message = await chain.ainvoke({"conversation": conversation, "query": query})
    except Exception:
        logger.exception("contextualize_query failed for query %r", query)
        raise

    standalone = message.content.strip() if isinstance(message.content, str) else ""
    return standalone or query


@traceable(name="contextualize_query")
async def contextualize_query(state: GraphState) -> dict:
    """The graph node: `query` becomes the standalone question; the typed text is kept for `record_turn`.

    No LLM call on a session's first turn, or with memory off — there is nothing
    to rewrite with. Fails open: if the rewrite errors, the turn goes on with
    the message as typed, which is what every turn did before memory existed.
    """
    query = state["query"]
    conversation = format_conversation(state)
    if not conversation:
        logger.info("contextualize_query: no earlier conversation, query unchanged")
        return {"user_message": query}

    try:
        standalone = await contextualize_query_core(query, conversation)
    except Exception:
        logger.warning("contextualize_query: rewrite failed, using the message as typed")
        return {"user_message": query}

    logger.info("contextualize_query: %r -> %r", query, standalone)
    return {"query": standalone, "user_message": query}
