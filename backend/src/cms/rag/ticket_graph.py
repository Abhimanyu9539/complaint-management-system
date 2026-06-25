"""The ticket graph: one run per ticket, separate from the chat graph.

    START -> input_guard -+-> END                                           (blocked)
                          +-> classify_ticket -> END                        (allowed)
                          +-> analyze_ticket -+-> retrieve_policies -+
                                              +-> retrieve_cases ----+-> join_retrieval
    join_retrieval -+-> END                                  (retrieval failed)
                    +-> ticket_no_match -> END               (no policy matched, no dept answer)
                    +-> draft_reply -+-> END                 (drafting failed)
                                     +-> ticket_output_guard -+-> END          (grounded, or still not)
                                                              +-> draft_reply  (ungrounded, first time)

It only computes. `services/ticket_pipeline.py` runs it and saves what it
produced, so status changes stay in `ticket_service`. No checkpointer: every run
starts from the ticket row, and its results live on the ticket.

A failing classifier, retriever or drafter records its error in `errors` rather
than raising, so the pipeline still saves what the other branch produced.
"""

import logging
from collections.abc import Awaitable, Callable
from functools import lru_cache
from pathlib import Path

from langgraph.graph import END, START, StateGraph
from langgraph.graph.state import CompiledStateGraph

from cms.rag.nodes.analyze_ticket import analyze_ticket
from cms.rag.nodes.classify_ticket import classify_ticket
from cms.rag.nodes.draft_reply import draft_reply
from cms.rag.nodes.input_guard import input_guard
from cms.rag.nodes.join_retrieval import join_retrieval
from cms.rag.nodes.retrieve_cases import retrieve_cases
from cms.rag.nodes.retrieve_policies import retrieve_policies
from cms.rag.nodes.ticket_no_match import ticket_no_match
from cms.rag.nodes.ticket_output_guard import ticket_output_guard
from cms.rag.subgraphs.complaint import route_after_output_guard
from cms.rag.ticket_state import TicketState, needs_holding_reply

logger = logging.getLogger(__name__)

# Node names
INPUT_GUARD = "input_guard"
CLASSIFY_TICKET = "classify_ticket"
ANALYZE_TICKET = "analyze_ticket"
RETRIEVE_POLICIES = "retrieve_policies"
RETRIEVE_CASES = "retrieve_cases"
JOIN_RETRIEVAL = "join_retrieval"
TICKET_NO_MATCH = "ticket_no_match"
DRAFT_REPLY = "draft_reply"
TICKET_OUTPUT_GUARD = "ticket_output_guard"

# Root run name in LangSmith.
TICKET_GRAPH_NAME = "ticket_run"

Node = Callable[[TicketState], Awaitable[dict]]


def _record_errors(stage: str, node: Node) -> Node:
    """Wrap `node` so an exception is recorded in `errors` instead of ending the run."""

    async def run(state: TicketState) -> dict:
        try:
            return await node(state)
        except Exception as exc:
            logger.exception("Ticket %s: %s failed", state.get("ticket_id"), stage)
            return {"errors": {stage: f"{type(exc).__name__}: {exc}"}}

    return run


def route_after_input_guard(state: TicketState) -> list[str] | str:
    """A blocked ticket goes no further; an allowed one is classified and drafted in parallel."""
    if state.get("input_blocked"):
        return END
    return [CLASSIFY_TICKET, ANALYZE_TICKET]


def route_after_retrieval(state: TicketState) -> str:
    """Stop if either retrieval failed; otherwise draft, or hold when there is nothing to draft from.

    A department's answer is enough to draft from even when no policy matched.
    """
    errors = state.get("errors", {})
    if RETRIEVE_POLICIES in errors or RETRIEVE_CASES in errors:
        return "failed"
    return "no_match_found" if needs_holding_reply(state) else "match_found"


def route_after_draft(state: TicketState) -> str:
    """A failed draft is not checked: the guard would send it back for a retry forever."""
    return "failed" if DRAFT_REPLY in state.get("errors", {}) else "drafted"


def route_after_ticket_guard(state: TicketState) -> str:
    """The chat lane's rule: pass, retry once, or give up.

    A thin wrapper so LangGraph reads `TicketState` from the signature; the
    chat function's `GraphState` hint would merge the chat channels in.
    """
    return route_after_output_guard(state)


def build_ticket_graph() -> CompiledStateGraph:
    """Wire the ticket graph. Built on every call, so tests can stub its nodes first."""
    builder = StateGraph(TicketState)

    # Chat nodes are typed for `GraphState`; without `input_schema` LangGraph would
    # merge those channels in. The `_record_errors` wrapper is typed for `TicketState`.
    builder.add_node(INPUT_GUARD, input_guard, input_schema=TicketState)
    builder.add_node(CLASSIFY_TICKET, _record_errors(CLASSIFY_TICKET, classify_ticket))
    builder.add_node(ANALYZE_TICKET, analyze_ticket)
    builder.add_node(RETRIEVE_POLICIES, _record_errors(RETRIEVE_POLICIES, retrieve_policies))
    builder.add_node(RETRIEVE_CASES, _record_errors(RETRIEVE_CASES, retrieve_cases))
    builder.add_node(JOIN_RETRIEVAL, join_retrieval, input_schema=TicketState)
    builder.add_node(TICKET_NO_MATCH, ticket_no_match)
    builder.add_node(DRAFT_REPLY, _record_errors(DRAFT_REPLY, draft_reply))
    builder.add_node(TICKET_OUTPUT_GUARD, ticket_output_guard)

    builder.add_edge(START, INPUT_GUARD)
    builder.add_conditional_edges(
        INPUT_GUARD, route_after_input_guard, [CLASSIFY_TICKET, ANALYZE_TICKET, END]
    )
    builder.add_edge(CLASSIFY_TICKET, END)
    builder.add_edge(ANALYZE_TICKET, RETRIEVE_POLICIES)
    builder.add_edge(ANALYZE_TICKET, RETRIEVE_CASES)
    builder.add_edge([RETRIEVE_POLICIES, RETRIEVE_CASES], JOIN_RETRIEVAL)
    builder.add_conditional_edges(
        JOIN_RETRIEVAL,
        route_after_retrieval,
        {
            "failed": END,
            "no_match_found": TICKET_NO_MATCH,
            "match_found": DRAFT_REPLY,
        },
    )
    builder.add_edge(TICKET_NO_MATCH, END)
    builder.add_conditional_edges(
        DRAFT_REPLY,
        route_after_draft,
        {
            "failed": END,
            "drafted": TICKET_OUTPUT_GUARD,
        },
    )
    builder.add_conditional_edges(
        TICKET_OUTPUT_GUARD,
        route_after_ticket_guard,
        {
            "grounded": END,
            "retry": DRAFT_REPLY,
            # Kept and saved as ungrounded; the gate sends it to review.
            "still_ungrounded": END,
        },
    )

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
