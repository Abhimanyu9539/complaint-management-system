"""`retrieve` — the graph's second node: no LLM, just the slice-1 hybrid
retriever driven by `analyze_query`'s output (build.md §0.3.2).

Named `retrieve_node`, not `retrieve`: `hybrid_retriever.retrieve` is imported
into this same module and the two names must not collide.
"""

import logging

from cms.config.settings import get_settings
from cms.rag.state import GraphState
from cms.retrieval.retrievers.hybrid_retriever import retrieve as hybrid_retrieve

logger = logging.getLogger(__name__)

# How many top candidates to widen to on low confidence — build.md §0.3.2's
# "widens the filter to top-2 departments."
WIDEN_TO = 2


def select_departments(
    candidates: list[dict], threshold: float
) -> list[str] | None:
    """The department filter for this retrieval, from `analyze_query`'s ranked
    candidates.

    Top-1 only when confident. Widens to the top `WIDEN_TO` candidates when
    the top-1 confidence is below `threshold` *and* a second candidate
    exists — widening to a list of one is a no-op, not a safety net. `None`
    (unfiltered) only when there are no candidates at all, which should not
    happen given `QueryAnalysis.department_candidates`'s `min_length=1`, but
    a node must not crash if it ever does.
    """
    if not candidates:
        return None
    if candidates[0]["confidence"] < threshold and len(candidates) > 1:
        return [c["department"] for c in candidates[:WIDEN_TO]]
    return [candidates[0]["department"]]


def retrieve_node(state: GraphState) -> dict:
    """Thin wrapper over `hybrid_retriever.retrieve`: pulls the rewritten
    queries and widened department filter out of state, and tracks the
    self-correction loop's attempt count.

    `search_queries` falls back to `[state["query"]]` so this node is
    callable with only `query` set — useful in isolation (tests, a future
    CLI probe) without having run `analyze_query` first.
    """
    settings = get_settings()
    queries = state.get("search_queries") or [state["query"]]
    departments = select_departments(
        state.get("department_candidates") or [], settings.dept_confidence_threshold
    )

    result = hybrid_retrieve(queries, departments=departments)

    return {
        "retrieved": result.chunks,
        "retrieval_attempts": state.get("retrieval_attempts", 0) + 1,
    }
