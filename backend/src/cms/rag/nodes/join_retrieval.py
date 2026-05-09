"""Complaint branch: wait for both retrievals, so the next branch sees policy and case hits.
"""

import logging

from langsmith import traceable

from cms.rag.state import GraphState

logger = logging.getLogger(__name__)


@traceable(name="join_retrieval")
async def join_retrieval(state: GraphState) -> dict:
    """The graph node: writes nothing; it only exists so routing runs after both retrievals.

    Without it, `retrieve_cases` could not see the `no_match` its sibling writes in
    the same step, and an edge straight to `generate` would run it next to `no_match`.
    """
    logger.info(
        "join_retrieval: %d policy chunk(s), %d case chunk(s)",
        len(state.get("policy_hits", [])),
        len(state.get("case_hits", [])),
    )
    return {}
