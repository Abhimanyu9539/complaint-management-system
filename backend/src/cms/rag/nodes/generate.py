"""Complaint branch: write the agent-facing draft from the retrieved policy chunks.
"""

import logging

from langchain_core.documents import Document
from langsmith import traceable

from cms.config.settings import get_settings
from cms.llm.chat.openrouter_chat import get_chat_model
from cms.llm.prompts.registry import load_prompt
from cms.rag.context import build_context, used_citations
from cms.rag.state import GraphState
from cms.schemas.generation import Citation

logger = logging.getLogger(__name__)


async def generate_core(
    query: str, hits: list[tuple[Document, float]]
) -> tuple[str, list[Citation]]:
    """A grounded draft for `query`, plus the citations it actually used.

    The one place the main model is paid for: this is the prose a support agent
    reads and acts on, and everything else in the graph is classification or
    retrieval that a cheap model does as well.

    Returns `used_citations`, not everything `build_context` offered — see that
    function for why.
    """
    settings = get_settings()
    context, citations = build_context(hits)
    prompt = load_prompt("generate")
    chain = prompt | get_chat_model(settings.openrouter_model_main)

    try:
        message = await chain.ainvoke({"context": context, "query": query})
    except Exception:
        logger.exception("generate failed for query %r (%d chunk(s))", query, len(citations))
        raise

    draft = message.content
    cited = used_citations(draft, citations)
    logger.info(
        "generate: %d chunk(s) in, %d cited, %d chars out", len(citations), len(cited), len(draft)
    )
    return draft, cited


@traceable(name="generate")
async def generate(state: GraphState) -> dict:
    """The graph node: a partial `GraphState` update."""
    draft, citations = await generate_core(state["query"], state.get("policy_hits", []))
    return {"draft": draft, "citations": citations}
