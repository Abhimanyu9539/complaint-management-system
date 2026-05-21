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


def format_feedback(reasons: list[str] | None, previous_draft: str | None = None) -> str:
    """The retry block: the draft that failed, then why it failed. Empty on a first draft."""
    if not reasons:
        return ""
    bullets = "\n".join(f"- {reason}" for reason in reasons)
    block = f"\n<feedback>\n{bullets}\n</feedback>\n"
    if previous_draft:
        block = f"\n<previous_draft>\n{previous_draft}\n</previous_draft>\n{block}"
    return block


async def generate_core(
    query: str,
    policy_hits: list[tuple[Document, float]],
    case_hits: list[tuple[Document, float]],
    feedback: list[str] | None = None,
    previous_draft: str | None = None,
) -> tuple[str, list[Citation]]:
    """A grounded draft for `query`, plus the citations it actually used.

    The one place the main model is paid for: this is the prose a support agent
    reads and acts on, and everything else in the graph is classification or
    retrieval that a cheap model does as well.

    Policy chunks and similar cases share one marker sequence, so a returned
    citation's `doc_type` says which corpus it came from.

    Returns `used_citations`, not everything `build_context` offered — see that
    function for why.

    `feedback` is the output guard's reasons on a regeneration and `previous_draft`
    the draft they apply to, so the model revises it rather than starting over.
    Prompt versions before v3 have no slot for either and ignore them.
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
                "feedback": format_feedback(feedback, previous_draft),
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
    pass gets the failed draft and the guard's reasons, and sets `regenerated`,
    which caps the loop at one retry. `output_guard` never changes `draft`, so on
    a retry it still holds the draft that failed.
    """
    retry = state.get("grounded") is False
    feedback = state.get("guard_reasons") if retry else None
    previous_draft = state.get("draft") if retry else None
    if retry:
        logger.info("generate: revising the failed draft with %d guard reason(s)", len(feedback or []))

    draft, citations = await generate_core(
        state["query"],
        state.get("policy_hits", []),
        state.get("case_hits", []),
        feedback=feedback,
        previous_draft=previous_draft,
    )
    update = {"draft": draft, "citations": citations}
    if retry:
        update["regenerated"] = True
    return update
