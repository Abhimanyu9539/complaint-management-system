"""Graph assembly: guard the input, analyze the query, fork on intent, then guard the draft.

    START -> input_guard -+-> blocked_input -> record_turn -> END
                          +-> analyze_query -+-> complaint lane
                                             +-> lookup lane
                                             +-> smalltalk -> record_turn -> END

    Complaint lane:
        retrieve_policies -+
                           +-> join_retrieval -+-> no_match -> record_turn -> END
        retrieve_cases ----+                   +-> generate -> output_guard -+-> record_turn -> END     (grounded)
                                                      ^                      +-> generate               (ungrounded, first time)
                                                      |______________________|
                                                                             +-> add_caveat -> record_turn -> END  (still ungrounded)

    Lookup lane:
        lookup_retrieve_policies -+
                                  +-> lookup_join_retrieval -+-> lookup_no_match -> record_turn -> END       (nothing relevant)
        lookup_retrieve_cases ----+                          +-> lookup_generate -> lookup_guard -+-> record_turn -> END  (grounded)
                                                                                                  +-> lookup_caveat -> record_turn -> END

A complaint runs retrieve_policies and retrieve_cases in parallel; join_retrieval
waits for both, so generate gets policy and case hits. A knowledge lookup is the
agent's own policy or case question, and its lane has the same shape: both
retrievals always run (the one `lookup_target` excludes returns empty), and
lookup_join_retrieval decides whether anything was found. Its guard does not
demand a policy citation, and it has no retry.

The two lanes share no node: each has its own retrieval, no-match and caveat, so
either can change without touching the other. Every path ends at record_turn,
which writes the turn into `chat_history` for the checkpointer. Exactly one
terminal runs per turn, so each gets its own edge — a list edge would build an
AND-join and wait forever.
"""

import logging
from functools import lru_cache
from pathlib import Path

from langgraph.checkpoint.base import BaseCheckpointSaver
from langgraph.graph import END, START, StateGraph
from langgraph.graph.state import CompiledStateGraph

from cms.db.mongo import get_checkpointer
from cms.rag.nodes.add_caveat import add_caveat
from cms.rag.nodes.analyze_query import analyze_query
from cms.rag.nodes.blocked_input import blocked_input
from cms.rag.nodes.generate import generate
from cms.rag.nodes.input_guard import input_guard
from cms.rag.nodes.join_retrieval import join_retrieval
from cms.rag.nodes.lookup_caveat import lookup_caveat
from cms.rag.nodes.lookup_generate import lookup_generate
from cms.rag.nodes.lookup_guard import lookup_guard
from cms.rag.nodes.lookup_join_retrieval import lookup_join_retrieval
from cms.rag.nodes.lookup_no_match import lookup_no_match
from cms.rag.nodes.lookup_retrieve_cases import lookup_retrieve_cases
from cms.rag.nodes.lookup_retrieve_policies import lookup_retrieve_policies
from cms.rag.nodes.no_match import no_match
from cms.rag.nodes.output_guard import output_guard
from cms.rag.nodes.record_turn import record_turn
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
RECORD_TURN = "record_turn"
LOOKUP_RETRIEVE_POLICIES = "lookup_retrieve_policies"
LOOKUP_RETRIEVE_CASES = "lookup_retrieve_cases"
LOOKUP_JOIN_RETRIEVAL = "lookup_join_retrieval"
LOOKUP_NO_MATCH = "lookup_no_match"
LOOKUP_GENERATE = "lookup_generate"
LOOKUP_GUARD = "lookup_guard"
LOOKUP_CAVEAT = "lookup_caveat"

COMPLAINT_QUERY = "complaint_query"
KNOWLEDGE_LOOKUP = "knowledge_lookup"
OTHER_QUERY = "other_query"


def route_after_input_guard(state: GraphState) -> str:
    """Determine the branch after `input_guard`: a blocked complaint goes no further."""
    return "blocked" if state.get("input_blocked") else "allowed"


def route_by_intent(state: GraphState) -> list[str] | str:
    """Determine the branch(es) after `analyze_query`: a complaint or a lookup searches policies and cases in parallel."""
    intent = state.get("intent")
    if intent == COMPLAINT_QUERY:
        return ["policy_search", "case_search"]
    if intent == KNOWLEDGE_LOOKUP:
        return ["lookup_policy_search", "lookup_case_search"]
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


def route_after_lookup_retrieval(state: GraphState) -> str:
    """Determine the branch after `lookup_join_retrieval`: nothing relevant in either corpus, or an answer."""
    return "no_match_found" if state.get("no_match") else "match_found"


def route_after_lookup_guard(state: GraphState) -> str:
    """Determine the branch after `lookup_guard`: pass, or caveat. No retry on this branch."""
    return "grounded" if state.get("grounded") is not False else "ungrounded"


def build_graph(checkpointer: BaseCheckpointSaver | None = None) -> CompiledStateGraph:
    """Wire the nodes and conditional branches using explicit path mappings.

    `checkpointer` defaults to None so a caller that only wants the shape — the
    CLI renderer, the flow tests — gets a graph that touches no database.
    """
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
    builder.add_node(RECORD_TURN, record_turn)
    builder.add_node(LOOKUP_RETRIEVE_POLICIES, lookup_retrieve_policies)
    builder.add_node(LOOKUP_RETRIEVE_CASES, lookup_retrieve_cases)
    builder.add_node(LOOKUP_JOIN_RETRIEVAL, lookup_join_retrieval)
    builder.add_node(LOOKUP_NO_MATCH, lookup_no_match)
    builder.add_node(LOOKUP_GENERATE, lookup_generate)
    builder.add_node(LOOKUP_GUARD, lookup_guard)
    builder.add_node(LOOKUP_CAVEAT, lookup_caveat)

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
            "lookup_policy_search": LOOKUP_RETRIEVE_POLICIES,
            "lookup_case_search": LOOKUP_RETRIEVE_CASES,
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
            "grounded": RECORD_TURN,
            "retry": GENERATE,
            "still_ungrounded": ADD_CAVEAT,
        },
    )

    # Lookup lane: same shape as the complaint lane, with its own nodes throughout.
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
            "grounded": RECORD_TURN,
            "ungrounded": LOOKUP_CAVEAT,
        },
    )

    # One edge each, never `add_edge([...], RECORD_TURN)`: a list start is an
    # AND-join, and only one of these ever runs.
    builder.add_edge(ADD_CAVEAT, RECORD_TURN)
    builder.add_edge(BLOCKED_INPUT, RECORD_TURN)
    builder.add_edge(NO_MATCH, RECORD_TURN)
    builder.add_edge(SMALLTALK, RECORD_TURN)
    builder.add_edge(LOOKUP_NO_MATCH, RECORD_TURN)
    builder.add_edge(LOOKUP_CAVEAT, RECORD_TURN)
    builder.add_edge(RECORD_TURN, END)

    return builder.compile(checkpointer=checkpointer)


@lru_cache
def get_graph() -> CompiledStateGraph:
    """The process-wide compiled graph, checkpointing to Mongo unless disabled."""
    return build_graph(get_checkpointer())


def render_graph() -> None:
    """Print the graph as Mermaid and save it as a PNG next to this module."""
    target = Path(__file__).with_suffix(".png")
    try:
        # `build_graph`, not `get_graph`: drawing the shape needs no database.
        graph = build_graph().get_graph()
        graph.draw_mermaid_png(output_file_path=str(target))
        logger.info("Graph png saved to %s", target)
    except Exception:
        logger.exception("Could not render the graph")


if __name__ == "__main__":
    render_graph()