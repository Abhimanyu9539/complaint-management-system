"""Lookup lane: answer the agent's own policy or case question.

    START -> lookup_retrieve_policies -+
    START -> lookup_retrieve_cases ----+-> lookup_join_retrieval -+-> lookup_no_match -> END       (nothing relevant)
                                                                 +-> lookup_generate -> lookup_guard -+-> END  (grounded)
                                                                                                      +-> lookup_caveat -> END

Both retrievals always run — the one `lookup_target` excludes returns empty — and
lookup_join_retrieval decides whether anything was found. The guard does not
demand a policy citation, and there is no retry. Compiled with
`checkpointer=False`, for the same reason as the complaint lane.
"""

import logging

from langgraph.graph import END, START, StateGraph
from langgraph.graph.state import CompiledStateGraph

from cms.rag.nodes.lookup_caveat import lookup_caveat
from cms.rag.nodes.lookup_generate import lookup_generate
from cms.rag.nodes.lookup_guard import lookup_guard
from cms.rag.nodes.lookup_join_retrieval import lookup_join_retrieval
from cms.rag.nodes.lookup_no_match import lookup_no_match
from cms.rag.nodes.lookup_retrieve_cases import lookup_retrieve_cases
from cms.rag.nodes.lookup_retrieve_policies import lookup_retrieve_policies
from cms.rag.state import GraphState

logger = logging.getLogger(__name__)

# Node names
LOOKUP_RETRIEVE_POLICIES = "lookup_retrieve_policies"
LOOKUP_RETRIEVE_CASES = "lookup_retrieve_cases"
LOOKUP_JOIN_RETRIEVAL = "lookup_join_retrieval"
LOOKUP_NO_MATCH = "lookup_no_match"
LOOKUP_GENERATE = "lookup_generate"
LOOKUP_GUARD = "lookup_guard"
LOOKUP_CAVEAT = "lookup_caveat"


def route_after_lookup_retrieval(state: GraphState) -> str:
    """Determine the branch after `lookup_join_retrieval`: nothing relevant in either corpus, or an answer."""
    return "no_match_found" if state.get("no_match") else "match_found"


def route_after_lookup_guard(state: GraphState) -> str:
    """Determine the branch after `lookup_guard`: pass, or caveat. No retry on this lane."""
    return "grounded" if state.get("grounded") is not False else "ungrounded"


def build_lookup_lane(checkpointer: bool | None = False) -> CompiledStateGraph:
    """Wire the lookup lane. Built on every call, so tests can stub its nodes first.

    `checkpointer` stays False at runtime, like the complaint lane. Only the
    drawing passes None, because LangGraph's xray skips a lane compiled with False.
    """
    builder = StateGraph(GraphState)

    builder.add_node(LOOKUP_RETRIEVE_POLICIES, lookup_retrieve_policies)
    builder.add_node(LOOKUP_RETRIEVE_CASES, lookup_retrieve_cases)
    builder.add_node(LOOKUP_JOIN_RETRIEVAL, lookup_join_retrieval)
    builder.add_node(LOOKUP_NO_MATCH, lookup_no_match)
    builder.add_node(LOOKUP_GENERATE, lookup_generate)
    builder.add_node(LOOKUP_GUARD, lookup_guard)
    builder.add_node(LOOKUP_CAVEAT, lookup_caveat)

    # Both retrievals start together; the join waits for both before deciding.
    builder.add_edge(START, LOOKUP_RETRIEVE_POLICIES)
    builder.add_edge(START, LOOKUP_RETRIEVE_CASES)
    builder.add_edge([LOOKUP_RETRIEVE_POLICIES, LOOKUP_RETRIEVE_CASES], LOOKUP_JOIN_RETRIEVAL)

    builder.add_conditional_edges(
        LOOKUP_JOIN_RETRIEVAL,
        route_after_lookup_retrieval,
        {
            "match_found": LOOKUP_GENERATE,
            "no_match_found": LOOKUP_NO_MATCH,
        },
    )

    builder.add_edge(LOOKUP_GENERATE, LOOKUP_GUARD)

    builder.add_conditional_edges(
        LOOKUP_GUARD,
        route_after_lookup_guard,
        {
            "grounded": END,
            "ungrounded": LOOKUP_CAVEAT,
        },
    )

    builder.add_edge(LOOKUP_NO_MATCH, END)
    builder.add_edge(LOOKUP_CAVEAT, END)

    return builder.compile(checkpointer=checkpointer)
