"""First graph node: classify the input, and for a complaint write policy-worded queries.
"""

import logging

from langsmith import traceable

from cms.config.settings import get_settings
from cms.llm.chat.openai_chat import get_chat_model
from cms.llm.prompts.registry import load_prompt
from cms.rag.state import GraphState
from cms.schemas.query_analysis import QueryAnalysis

logger = logging.getLogger(__name__)


async def analyze_query_core(query: str) -> QueryAnalysis:
    """Classify `query` and rewrite it into policy-worded retrieval queries."""
    settings = get_settings()
    prompt = load_prompt("analyze_query")
    model = get_chat_model(settings.openai_model_cheap).with_structured_output(QueryAnalysis)
    chain = prompt | model

    try:
        analysis = await chain.ainvoke({"query": query})
    except Exception:
        logger.exception("analyze_query failed for query %r", query)
        raise

    logger.info(
        "analyze_query: intent=%s, %d policy query(ies) for %r",
        analysis.intent,
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
    if analysis.intent != "complaint_query":
        return []
    return [query, *analysis.policy_queries]


@traceable(name="analyze_query")
async def analyze_query(state: GraphState) -> dict:
    """The graph node: a partial `GraphState` update."""
    analysis = await analyze_query_core(state["query"])
    return {
        "intent": analysis.intent,
        "policy_queries": build_policy_queries(state["query"], analysis),
    }
