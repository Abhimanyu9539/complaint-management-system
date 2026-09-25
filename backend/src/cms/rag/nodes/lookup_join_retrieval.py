"""Lookup branch: wait for both retrievals, then decide whether anything relevant was found.
"""

import logging

from langsmith import traceable

from cms.rag.state import GraphState

logger = logging.getLogger(__name__)


@traceable(name="lookup_join_retrieval")
async def lookup_join_retrieval(state: GraphState) -> dict:
    """The graph node: sets `no_match` when neither corpus returned anything.

    The decision lives here, not in the retrieval nodes: each one only sees its own
    corpus, and two parallel nodes cannot both write `no_match` in the same step.
    """
    policy_hits = state.get("policy_hits", [])
    case_hits = state.get("case_hits", [])
    logger.info(
        "lookup_join_retrieval: %d policy chunk(s), %d case chunk(s)",
        len(policy_hits),
        len(case_hits),
    )
    return {"no_match": not policy_hits and not case_hits}
