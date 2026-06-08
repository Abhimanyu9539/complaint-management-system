"""Lookup branch: answer the agent's own policy or case question from what was retrieved.
"""

import logging

from langchain_core.documents import Document
from langsmith import traceable

from cms.config.settings import get_settings
from cms.llm.chat.openrouter_chat import get_chat_model
from cms.llm.prompts.registry import load_prompt
from cms.rag.context import build_generation_context, used_citations
from cms.rag.state import GraphState
from cms.schemas.generation import Citation

logger = logging.getLogger(__name__)


async def lookup_generate_core(
    query: str,
    policy_hits: list[tuple[Document, float]],
    case_hits: list[tuple[Document, float]],
) -> tuple[str, list[Citation]]:
    """A cited answer to `query`, plus the citations it actually used.

    Same context block and marker sequence as `generate_core`, so either section
    may be empty — a cases-only lookup numbers its cases from [1].
    """
    settings = get_settings()
    context, cases, citations = build_generation_context(policy_hits, case_hits)
    prompt = load_prompt("lookup", settings.lookup_prompt_version)
    chain = prompt | get_chat_model(settings.openrouter_model_main)

    try:
        message = await chain.ainvoke({"context": context, "cases": cases, "query": query})
    except Exception:
        logger.exception("lookup_generate failed for query %r (%d chunk(s))", query, len(citations))
        raise

    answer = message.content
    cited = used_citations(answer, citations)
    logger.info(
        "lookup_generate: %d policy + %d case chunk(s) in, %d cited, %d chars out",
        len(policy_hits),
        len(case_hits),
        len(cited),
        len(answer),
    )
    return answer, cited


@traceable(name="lookup_generate")
async def lookup_generate(state: GraphState) -> dict:
    """The graph node: writes `draft`, the slot every branch fills. Runs once — no retry."""
    answer, citations = await lookup_generate_core(
        state["query"],
        state.get("policy_hits", []),
        state.get("case_hits", []),
    )
    return {"draft": answer, "citations": citations}
