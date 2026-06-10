"""Complaint lane: resolve one customer's complaint from policy and past cases.

    START -> retrieve_policies -+
    START -> retrieve_cases ----+-> join_retrieval -+-> no_match -> END
                                                    +-> generate -> output_guard -+-> END           (grounded)
                                                           ^                      +-> generate      (ungrounded, first time)
                                                           |______________________|
                                                                                  +-> add_caveat -> END  (still ungrounded)

Both retrievals run in parallel; join_retrieval waits for both, so generate gets
policy and case hits. Compiled with `checkpointer=False`: the parent graph stores
the turn, and a lane checkpoint would persist the retrieved chunks record_turn clears.
"""

import logging

from langgraph.graph import END, START, StateGraph
from langgraph.graph.state import CompiledStateGraph

from cms.rag.nodes.add_caveat import add_caveat
from cms.rag.nodes.generate import generate
from cms.rag.nodes.join_retrieval import join_retrieval
from cms.rag.nodes.no_match import no_match
from cms.rag.nodes.output_guard import output_guard
from cms.rag.nodes.retrieve_cases import retrieve_cases
from cms.rag.nodes.retrieve_policies import retrieve_policies
from cms.rag.state import GraphState

logger = logging.getLogger(__name__)

# Node names
RETRIEVE_POLICIES = "retrieve_policies"
RETRIEVE_CASES = "retrieve_cases"
JOIN_RETRIEVAL = "join_retrieval"
NO_MATCH = "no_match"
GENERATE = "generate"
OUTPUT_GUARD = "output_guard"
ADD_CAVEAT = "add_caveat"


def route_after_retrieval(state: GraphState) -> str:
    """Determine the branch after `join_retrieval` based on the policy match result."""
    return "no_match_found" if state.get("no_match") else "match_found"


def route_after_output_guard(state: GraphState) -> str:
    """Determine the branch after `output_guard`: pass, retry once, or caveat.

    `grounded` is None when guardrails are disabled, which passes. The retry is
    capped by `regenerated`, which `generate` sets on its second run.
    """
    if state.get("grounded") is not False:
        return "grounded"
    if not state.get("regenerated"):
        return "retry"
    return "still_ungrounded"


def build_complaint_lane(checkpointer: bool | None = False) -> CompiledStateGraph:
    """Wire the complaint lane. Built on every call, so tests can stub its nodes first.

    `checkpointer` stays False at runtime (see the module docstring). Only the
    drawing passes None, because LangGraph's xray skips a lane compiled with False.
    """
    builder = StateGraph(GraphState)

    builder.add_node(RETRIEVE_POLICIES, retrieve_policies)
    builder.add_node(RETRIEVE_CASES, retrieve_cases)
    builder.add_node(JOIN_RETRIEVAL, join_retrieval)
    builder.add_node(NO_MATCH, no_match)
    builder.add_node(GENERATE, generate)
    builder.add_node(OUTPUT_GUARD, output_guard)
    builder.add_node(ADD_CAVEAT, add_caveat)

    # Both retrievals start together; the join waits for both before deciding.
    builder.add_edge(START, RETRIEVE_POLICIES)
    builder.add_edge(START, RETRIEVE_CASES)
    builder.add_edge([RETRIEVE_POLICIES, RETRIEVE_CASES], JOIN_RETRIEVAL)

    builder.add_conditional_edges(
        JOIN_RETRIEVAL,
        route_after_retrieval,
        {
            "match_found": GENERATE,
            "no_match_found": NO_MATCH,
        },
    )

    builder.add_edge(GENERATE, OUTPUT_GUARD)

    builder.add_conditional_edges(
        OUTPUT_GUARD,
        route_after_output_guard,
        {
            "grounded": END,
            "retry": GENERATE,
            "still_ungrounded": ADD_CAVEAT,
        },
    )

    builder.add_edge(NO_MATCH, END)
    builder.add_edge(ADD_CAVEAT, END)

    return builder.compile(checkpointer=checkpointer)
