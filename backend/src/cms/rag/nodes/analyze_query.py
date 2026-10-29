"""First graph node: classify the input, and for a complaint or lookup write policy-worded queries.

On a follow-up turn the same call also rewrites the message into a standalone question.
"""

import logging

from langsmith import traceable
from pydantic import BaseModel

from cms.config.settings import get_settings
from cms.llm.chat.openrouter_chat import get_chat_model
from cms.llm.prompts.registry import load_prompt
from cms.rag.memory import format_conversation
from cms.rag.state import GraphState
from cms.schemas.query_analysis import QueryAnalysis, TurnAnalysis

logger = logging.getLogger(__name__)


async def _run(schema: type[BaseModel], query: str, conversation: str = "") -> BaseModel:
    """One cheap-model call on the `analyze_query` prompt, parsed into `schema`."""
    settings = get_settings()
    prompt = load_prompt("analyze_query", settings.analyze_query_prompt_version)
    model = get_chat_model(settings.openrouter_model_cheap).with_structured_output(schema)
    chain = prompt | model

    try:
        return await chain.ainvoke({"query": query, "conversation": conversation})
    except Exception:
        logger.exception("analyze_query failed for query %r", query)
        raise


def _log_analysis(query: str, analysis: QueryAnalysis) -> None:
    logger.info(
        "analyze_query: intent=%s, lookup_target=%s, risk_flags=%s, %d policy query(ies) for %r",
        analysis.intent,
        analysis.lookup_target,
        analysis.risk_flags,
        len(analysis.policy_queries),
        query,
    )
    for policy_query in analysis.policy_queries:
        logger.info("  - %s", policy_query)


async def analyze_query_core(query: str) -> QueryAnalysis:
    """Classify `query`, flag its risks, and rewrite it into policy-worded retrieval queries."""
    analysis = await _run(QueryAnalysis, query)
    _log_analysis(query, analysis)
    return analysis


async def analyze_turn_core(query: str, conversation: str) -> tuple[str, QueryAnalysis]:
    """A follow-up: `query` made standalone using `conversation`, and the analysis of that.

    The standalone question is `query` itself when the model left it empty — it
    does that for a message that needs no rewriting.
    """
    turn = await _run(TurnAnalysis, query, conversation)
    standalone = turn.standalone_query.strip() or query
    logger.info("analyze_query: %r -> %r", query, standalone)
    _log_analysis(standalone, turn.analysis)
    return standalone, turn.analysis


def build_policy_queries(query: str, analysis: QueryAnalysis) -> list[str]:
    """The original query plus the rewrites — what retrieval searches with.

    The original is kept because a rewrite can drift from what the user actually asked.
    Nothing to retrieve for smalltalk, so that returns empty.
    """
    if analysis.intent not in ("complaint_query", "knowledge_lookup"):
        return []
    return [query, *analysis.policy_queries]


async def _analyze(state: GraphState) -> tuple[str, QueryAnalysis]:
    """The question the lanes work on, and its analysis.

    No conversation on a session's first turn, or with memory off, so the
    message is analyzed as typed. If the follow-up call fails, the turn goes on
    the same way: with the message as typed.
    """
    typed = state["query"]
    conversation = format_conversation(state)
    if conversation:
        try:
            return await analyze_turn_core(typed, conversation)
        except Exception:
            logger.warning(
                "analyze_query: follow-up analysis failed, using the message as typed", exc_info=True
            )
    return typed, await analyze_query_core(typed)


@traceable(name="analyze_query")
async def analyze_query(state: GraphState) -> dict:
    """The graph node: `query` becomes the standalone question; the typed text is kept for `record_turn`."""
    query, analysis = await _analyze(state)
    # Only a complaint has a reply for a lead to review; a flag on a lookup is noise.
    risk_flags = analysis.risk_flags if analysis.intent == "complaint_query" else []
    return {
        "query": query,
        "user_message": state["query"],
        "intent": analysis.intent,
        "lookup_target": analysis.lookup_target,
        "policy_queries": build_policy_queries(query, analysis),
        "risk_flags": risk_flags,
        # Any flag means a lead reviews the reply before it is sent (ai §4).
        "requires_lead_review": bool(risk_flags),
    }
