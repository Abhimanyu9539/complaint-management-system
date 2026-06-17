"""Ticket-graph node: write the policy-worded queries retrieval searches with, and flag risks.
"""

import logging

from langsmith import traceable

from cms.rag.nodes.analyze_query import analyze_query_core
from cms.rag.ticket_state import TicketState

logger = logging.getLogger(__name__)


@traceable(name="analyze_ticket")
async def analyze_ticket(state: TicketState) -> dict:
    """The ticket-graph node: the original text plus the rewrites, whatever the intent.

    A ticket is always a complaint, so the intent is not used. If the call fails,
    retrieval runs on the original text alone: the rewrites only help it.
    """
    query = state["query"]
    try:
        analysis = await analyze_query_core(query)
    except Exception:
        logger.warning("analyze_ticket: analysis failed, searching with the original text only")
        return {"policy_queries": [query], "risk_flags": []}

    return {
        "policy_queries": [query, *analysis.policy_queries],
        "risk_flags": analysis.risk_flags,
    }
