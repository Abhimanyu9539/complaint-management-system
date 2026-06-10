"""Graph assembly: guard the input, analyze the query, hand it to one lane, record the turn.

    START -> input_guard -+-> blocked_input ------------------------------+
                          +-> analyze_query -+-> complaint_lane ----------+
                                             +-> lookup_lane -------------+-> record_turn -> END
                                             +-> smalltalk ---------------+

Each lane is a compiled subgraph with its own nodes — see `rag/subgraphs/complaint.py`
and `rag/subgraphs/lookup.py` for their wiring. They share no node, so either can
change without touching the other.

Every path ends at record_turn, which writes the turn into `chat_history` for the
checkpointer. Exactly one branch runs per turn, so each gets its own edge — a list
edge would build an AND-join and wait forever.

Streaming a lane's tokens needs `astream(..., subgraphs=True)`: LangGraph drops
messages from inside a subgraph without it. See `services/chat_service.py`.
"""

import logging
from functools import lru_cache
from pathlib import Path

from langchain_core.runnables.graph import Graph
from langgraph.checkpoint.base import BaseCheckpointSaver
from langgraph.graph import END, START, StateGraph
from langgraph.graph.state import CompiledStateGraph

from cms.db.mongo import get_checkpointer
from cms.rag.nodes.analyze_query import analyze_query
from cms.rag.nodes.blocked_input import blocked_input
from cms.rag.nodes.input_guard import input_guard
from cms.rag.nodes.record_turn import record_turn
from cms.rag.nodes.smalltalk import smalltalk
from cms.rag.state import GraphState
from cms.rag.subgraphs.complaint import build_complaint_lane
from cms.rag.subgraphs.lookup import build_lookup_lane

logger = logging.getLogger(__name__)

# Node names
INPUT_GUARD = "input_guard"
BLOCKED_INPUT = "blocked_input"
ANALYZE_QUERY = "analyze_query"
COMPLAINT_LANE = "complaint_lane"
LOOKUP_LANE = "lookup_lane"
SMALLTALK = "smalltalk"
RECORD_TURN = "record_turn"

COMPLAINT_QUERY = "complaint_query"
KNOWLEDGE_LOOKUP = "knowledge_lookup"


def route_after_input_guard(state: GraphState) -> str:
    """Determine the branch after `input_guard`: a blocked complaint goes no further."""
    return "blocked" if state.get("input_blocked") else "allowed"


def route_by_intent(state: GraphState) -> str:
    """Determine the lane after `analyze_query`. Each lane starts its own retrievals."""
    intent = state.get("intent")
    if intent == COMPLAINT_QUERY:
        return "complaint"
    if intent == KNOWLEDGE_LOOKUP:
        return "lookup"
    return "other_query"


def build_graph(
    checkpointer: BaseCheckpointSaver | None = None,
    lane_checkpointer: bool | None = False,
) -> CompiledStateGraph:
    """Wire the parent graph; the lanes are built here too, so tests can stub their nodes first.

    `checkpointer` defaults to None so a caller that only wants the shape — the
    CLI renderer, the flow tests — gets a graph that touches no database.
    `lane_checkpointer` stays False except for `render_graph` — see there.
    """
    builder = StateGraph(GraphState)

    # Register nodes — a lane is one node holding its whole subgraph.
    builder.add_node(INPUT_GUARD, input_guard)
    builder.add_node(BLOCKED_INPUT, blocked_input)
    builder.add_node(ANALYZE_QUERY, analyze_query)
    builder.add_node(COMPLAINT_LANE, build_complaint_lane(lane_checkpointer))
    builder.add_node(LOOKUP_LANE, build_lookup_lane(lane_checkpointer))
    builder.add_node(SMALLTALK, smalltalk)
    builder.add_node(RECORD_TURN, record_turn)

    builder.add_edge(START, INPUT_GUARD)

    builder.add_conditional_edges(
        INPUT_GUARD,
        route_after_input_guard,
        {
            "allowed": ANALYZE_QUERY,
            "blocked": BLOCKED_INPUT,
        },
    )

    builder.add_conditional_edges(
        ANALYZE_QUERY,
        route_by_intent,
        {
            "complaint": COMPLAINT_LANE,
            "lookup": LOOKUP_LANE,
            "other_query": SMALLTALK,
        },
    )

    # One edge each, never `add_edge([...], RECORD_TURN)`: a list start is an
    # AND-join, and only one of these ever runs.
    builder.add_edge(BLOCKED_INPUT, RECORD_TURN)
    builder.add_edge(COMPLAINT_LANE, RECORD_TURN)
    builder.add_edge(LOOKUP_LANE, RECORD_TURN)
    builder.add_edge(SMALLTALK, RECORD_TURN)
    builder.add_edge(RECORD_TURN, END)

    return builder.compile(checkpointer=checkpointer)


@lru_cache
def get_graph() -> CompiledStateGraph:
    """The process-wide compiled graph, checkpointing to Mongo unless disabled."""
    return build_graph(get_checkpointer())


def build_drawing() -> Graph:
    """The whole graph with each lane's nodes expanded, for drawing only.

    LangGraph's xray skips subgraphs compiled with `checkpointer=False`, so the
    lanes are built with None here. This graph is drawn, never run, so nothing is
    stored — and with no parent checkpointer it touches no database.
    """
    return build_graph(lane_checkpointer=None).get_graph(xray=True)


def render_graph() -> None:
    """Save the whole graph, lanes expanded, as a PNG next to this module."""
    target = Path(__file__).with_suffix(".png")
    try:
        build_drawing().draw_mermaid_png(output_file_path=str(target))
        logger.info("Graph png saved to %s", target)
    except Exception:
        logger.exception("Could not render the graph")


if __name__ == "__main__":
    render_graph()
