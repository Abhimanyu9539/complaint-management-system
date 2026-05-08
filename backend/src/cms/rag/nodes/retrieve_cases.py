"""Complaint branch: find past resolved cases similar to the customer's complaint.
"""

import logging

from langsmith import traceable

from cms.rag.state import GraphState
from cms.retrieval.retrievers.case_retriever import retrieve_cases_hybrid

logger = logging.getLogger(__name__)


@traceable(name="retrieve_cases")
async def retrieve_cases(state: GraphState) -> dict:
    """The graph node: a partial `GraphState` update.

    Searches with the customer's own wording, not `policy_queries` — cases are
    stored as complaint text, so the original query is the closer match.
    """
    query = state["query"]
    try:
        hits = await retrieve_cases_hybrid(query)
    except Exception:
        logger.exception("Case retrieval failed for query %r", query)
        raise

    logger.info("retrieve_cases: %d case chunk(s) for %r", len(hits), query)
    return {"case_hits": hits}
