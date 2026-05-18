"""Complaint branch: write the agent-facing draft from the retrieved policy chunks and similar cases.
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


def format_feedback(reasons: list[str] | None) -> str:
    """The prompt's <feedback> block: why the last draft failed. Empty on a first draft."""
    if not reasons:
        return ""
    bullets = "\n".join(f"- {reason}" for reason in reasons)
    return f"\n<feedback>\n{bullets}\n</feedback>\n"


async def generate_core(
    query: str,
    policy_hits: list[tuple[Document, float]],
    case_hits: list[tuple[Document, float]],
    feedback: list[str] | None = None,
) -> tuple[str, list[Citation]]:
    """A grounded draft for `query`, plus the citations it actually used.

    The one place the main model is paid for: this is the prose a support agent
    reads and acts on, and everything else in the graph is classification or
    retrieval that a cheap model does as well.

    Policy chunks and similar cases share one marker sequence, so a returned
    citation's `doc_type` says which corpus it came from.

    Returns `used_citations`, not everything `build_context` offered — see that
    function for why.

    `feedback` is the output guard's reasons on a regeneration. Prompt versions
    before v3 have no slot for it and ignore it.
    """
    settings = get_settings()
    context, cases, citations = build_generation_context(policy_hits, case_hits)
    prompt = load_prompt("generate", settings.generate_prompt_version)
    chain = prompt | get_chat_model(settings.openrouter_model_main)

    try:
        message = await chain.ainvoke(
            {
                "context": context,
                "cases": cases,
                "query": query,
                "feedback": format_feedback(feedback),
            }
        )
    except Exception:
        logger.exception("generate failed for query %r (%d chunk(s))", query, len(citations))
        raise

    draft = message.content
    cited = used_citations(draft, citations)
    logger.info(
        "generate: %d policy + %d case chunk(s) in, %d cited, %d chars out",
        len(policy_hits),
        len(case_hits),
        len(cited),
        len(draft),
    )
    return draft, cited


@traceable(name="generate")
async def generate(state: GraphState) -> dict:
    """The graph node: a partial `GraphState` update.

    Runs a second time only when `output_guard` marked the draft ungrounded; that
    pass gets the guard's reasons as feedback and sets `regenerated`, which caps
    the loop at one retry.
    """
    retry = state.get("grounded") is False
    feedback = state.get("guard_reasons") if retry else None
    if retry:
        logger.info("generate: regenerating with %d guard reason(s)", len(feedback or []))

    draft, citations = await generate_core(
        state["query"], state.get("policy_hits", []), state.get("case_hits", []), feedback=feedback
    )
    update = {"draft": draft, "citations": citations}
    if retry:
        update["regenerated"] = True
    return update
