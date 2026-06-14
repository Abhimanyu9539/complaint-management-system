"""The ticket graph: one run per ticket, separate from the chat graph.

    START -> input_guard -+-> classify_ticket -> END   (allowed)
                          +-> END                     (blocked)

It only computes. `services/ticket_pipeline.py` runs it and saves what it
produced, so status changes stay in `ticket_service`. No checkpointer: every run
starts from the ticket row, and its results live on the ticket.
"""

import logging
from functools import lru_cache
from pathlib import Path

from langgraph.graph import END, START, StateGraph
from langgraph.graph.state import CompiledStateGraph

from cms.rag.nodes.classify_ticket import classify_ticket
from cms.rag.nodes.input_guard import input_guard
from cms.rag.ticket_state import TicketState

logger = logging.getLogger(__name__)

# Node names
INPUT_GUARD = "input_guard"
CLASSIFY_TICKET = "classify_ticket"

# Root run name in LangSmith.
TICKET_GRAPH_NAME = "ticket_run"


def route_after_input_guard(state: TicketState) -> str:
    """A blocked ticket goes no further; a person handles it."""
    return "blocked" if state.get("input_blocked") else "allowed"


def build_ticket_graph() -> CompiledStateGraph:
    """Wire the ticket graph. Built on every call, so tests can stub its nodes first."""
    builder = StateGraph(TicketState)

    builder.add_node(INPUT_GUARD, input_guard)
    builder.add_node(CLASSIFY_TICKET, classify_ticket)

    builder.add_edge(START, INPUT_GUARD)
    builder.add_conditional_edges(
        INPUT_GUARD,
        route_after_input_guard,
        {
            "allowed": CLASSIFY_TICKET,
            "blocked": END,
        },
    )
    builder.add_edge(CLASSIFY_TICKET, END)

    return builder.compile(name=TICKET_GRAPH_NAME)


@lru_cache
def get_ticket_graph() -> CompiledStateGraph:
    """The process-wide compiled ticket graph."""
    return build_ticket_graph()


def render_ticket_graph() -> None:
    """Save the ticket graph as a PNG next to this module."""
    target = Path(__file__).with_suffix(".png")
    try:
        build_ticket_graph().get_graph().draw_mermaid_png(output_file_path=str(target))
        logger.info("Ticket graph png saved to %s", target)
    except Exception:
        logger.exception("Could not render the ticket graph")


if __name__ == "__main__":
    render_ticket_graph()


