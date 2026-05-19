"""Graph assembly: guard the input, analyze the query, fork on intent, then guard the draft.

    START -> input_guard -+-> blocked_input -> END
                          +-> analyze_query -+-> retrieve_policies -+
                                             |                      +-> join_retrieval -+
                                             +-> retrieve_cases ----+                   |
                                             +-> smalltalk -> END                       |
                                                                                        |
        +-- no_match -> END  <----------------------------------------------------------+
        +-- generate -> output_guard -+-> END                  (grounded)
               ^                      +-> generate             (ungrounded, first time)
               |______________________|
                                      +-> add_caveat -> END    (ungrounded after the retry)

A complaint runs retrieve_policies and retrieve_cases in parallel; join_retrieval
waits for both, so generate gets policy and case hits.
"""

import logging
from functools import lru_cache
from pathlib import Path

from langgraph.graph import END, START, StateGraph
from langgraph.graph.state import CompiledStateGraph

from cms.rag.nodes.add_caveat import add_caveat
from cms.rag.nodes.analyze_query import analyze_query
from cms.rag.nodes.blocked_input import blocked_input
from cms.rag.nodes.generate import generate
from cms.rag.nodes.input_guard import input_guard
from cms.rag.nodes.join_retrieval import join_retrieval
from cms.rag.nodes.no_match import no_match
from cms.rag.nodes.output_guard import output_guard
from cms.rag.nodes.retrieve_cases import retrieve_cases
from cms.rag.nodes.retrieve_policies import retrieve_policies
from cms.rag.nodes.smalltalk import smalltalk
from cms.rag.state import GraphState

logger = logging.getLogger(__name__)

# Node names
INPUT_GUARD = "input_guard"
BLOCKED_INPUT = "blocked_input"
ANALYZE_QUERY = "analyze_query"
RETRIEVE_POLICIES = "retrieve_policies"
RETRIEVE_CASES = "retrieve_cases"
JOIN_RETRIEVAL = "join_retrieval"
SMALLTALK = "smalltalk"
NO_MATCH = "no_match"
GENERATE = "generate"
OUTPUT_GUARD = "output_guard"
ADD_CAVEAT = "add_caveat"

COMPLAINT_QUERY = "complaint_query"
OTHER_QUERY = "other_query"


def route_after_input_guard(state: GraphState) -> str:
    """Determine the branch after `input_guard`: a blocked complaint goes no further."""
    return "blocked" if state.get("input_blocked") else "allowed"


def route_by_intent(state: GraphState) -> list[str] | str:
    """Determine the branch(es) after `analyze_query`: a complaint searches policies and cases in parallel."""
    if state.get("intent") == "complaint_query":
        return ["policy_search", "case_search"]
    return "other_query"


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


def build_graph() -> CompiledStateGraph:
    """Wire the nodes and conditional branches using explicit path mappings."""
    builder = StateGraph(GraphState)

    # Register nodes
    builder.add_node(INPUT_GUARD, input_guard)
    builder.add_node(BLOCKED_INPUT, blocked_input)
    builder.add_node(ANALYZE_QUERY, analyze_query)
    builder.add_node(RETRIEVE_POLICIES, retrieve_policies)
    builder.add_node(RETRIEVE_CASES, retrieve_cases)
    builder.add_node(JOIN_RETRIEVAL, join_retrieval)
    builder.add_node(SMALLTALK, smalltalk)
    builder.add_node(NO_MATCH, no_match)
    builder.add_node(GENERATE, generate)
    builder.add_node(OUTPUT_GUARD, output_guard)
    builder.add_node(ADD_CAVEAT, add_caveat)

    # Linear and conditional edges
    builder.add_edge(START, INPUT_GUARD)

    builder.add_conditional_edges(
        INPUT_GUARD,
        route_after_input_guard,
        {
            "allowed": ANALYZE_QUERY,
            "blocked": BLOCKED_INPUT,
        },
    )

    # Intent-based branching on the edge from analyze_query
    builder.add_conditional_edges(
        ANALYZE_QUERY, 
        route_by_intent, 
        {
            "policy_search": RETRIEVE_POLICIES,
            "case_search": RETRIEVE_CASES,
            "other_query": SMALLTALK,
        }
    )
    
    # Waits for both retrievals before the one match/no-match decision.
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

    builder.add_edge(ADD_CAVEAT, END)
    builder.add_edge(BLOCKED_INPUT, END)
    builder.add_edge(NO_MATCH, END)
    builder.add_edge(SMALLTALK, END)
    
    return builder.compile()


@lru_cache
def get_graph() -> CompiledStateGraph:
    """The process-wide compiled graph."""
    return build_graph()


def render_graph() -> None:
    """Print the graph as Mermaid and save it as a PNG next to this module."""
    target = Path(__file__).with_suffix(".png")
    try:
        graph = get_graph().get_graph()
        graph.draw_mermaid_png(output_file_path=str(target))
        logger.info("Graph png saved to %s", target)
    except Exception:
        logger.exception("Could not render the graph")


if __name__ == "__main__":
    render_graph()