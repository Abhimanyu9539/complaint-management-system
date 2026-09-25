"""First graph node: classify the input, and for a complaint or lookup write policy-worded queries.
"""

import logging

from langsmith import traceable

from cms.config.settings import get_settings
from cms.llm.chat.openrouter_chat import get_chat_model
from cms.llm.prompts.registry import load_prompt
from cms.rag.state import GraphState
from cms.schemas.query_analysis import QueryAnalysis

logger = logging.getLogger(__name__)


async def analyze_query_core(query: str) -> QueryAnalysis:
    """Classify `query`, flag its risks, and rewrite it into policy-worded retrieval queries."""
    settings = get_settings()
    prompt = load_prompt("analyze_query", settings.analyze_query_prompt_version)
    model = get_chat_model(settings.openrouter_model_cheap).with_structured_output(QueryAnalysis)
    chain = prompt | model

    try:
        analysis = await chain.ainvoke({"query": query})
    except Exception:
        logger.exception("analyze_query failed for query %r", query)
        raise

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
    return analysis


def build_policy_queries(query: str, analysis: QueryAnalysis) -> list[str]:
    """The original query plus the rewrites — what retrieval searches with.

    The original is kept because a rewrite can drift from what the user actually asked.
    Nothing to retrieve for smalltalk, so that returns empty.
    """
    if analysis.intent not in ("complaint_query", "knowledge_lookup"):
        return []
    return [query, *analysis.policy_queries]


@traceable(name="analyze_query")
async def analyze_query(state: GraphState) -> dict:
    """The graph node: a partial `GraphState` update."""
    analysis = await analyze_query_core(state["query"])
    # Only a complaint has a reply for a lead to review; a flag on a lookup is noise.
    risk_flags = analysis.risk_flags if analysis.intent == "complaint_query" else []
    return {
        "intent": analysis.intent,
        "lookup_target": analysis.lookup_target,
        "policy_queries": build_policy_queries(state["query"], analysis),
        "risk_flags": risk_flags,
        # Any flag means a lead reviews the reply before it is sent (ai §4).
        "requires_lead_review": bool(risk_flags),
    }
