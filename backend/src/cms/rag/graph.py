"""Graph assembly: analyze the query, then fork on intent using conditional edge branches.

    START -> analyze_query -+-> retrieve_policies -+-> generate  -> END
                            |                     +-> no_match -> END
                            +-> smalltalk         -> END
"""

import logging
from functools import lru_cache
from pathlib import Path

from langgraph.graph import END, START, StateGraph
from langgraph.graph.state import CompiledStateGraph

from cms.rag.nodes.analyze_query import analyze_query
from cms.rag.nodes.generate import generate
from cms.rag.nodes.no_match import no_match
from cms.rag.nodes.retrieve_policies import retrieve_policies
from cms.rag.nodes.smalltalk import smalltalk
from cms.rag.state import GraphState

logger = logging.getLogger(__name__)

# Node names
ANALYZE_QUERY = "analyze_query"
RETRIEVE_POLICIES = "retrieve_policies"
SMALLTALK = "smalltalk"
NO_MATCH = "no_match"
GENERATE = "generate"

COMPLAINT_QUERY = "complaint_query"
OTHER_QUERY = "other_query"


def route_by_intent(state: GraphState) -> str:
    """Determine the branch after `analyze_query` based on user intent."""
    return "complaint_query" if state.get("intent") == "complaint_query" else "other_query"


def route_after_retrieval(state: GraphState) -> str:
    """Determine the branch after `retrieve_policies` based on match results."""
    return "no_match_found" if state.get("no_match") else "match_found"


def build_graph() -> CompiledStateGraph:
    """Wire the nodes and conditional branches using explicit path mappings."""
    builder = StateGraph(GraphState)

    # Register nodes
    builder.add_node(ANALYZE_QUERY, analyze_query)
    builder.add_node(RETRIEVE_POLICIES, retrieve_policies)
    builder.add_node(SMALLTALK, smalltalk)
    builder.add_node(NO_MATCH, no_match)
    builder.add_node(GENERATE, generate)

    # Linear and conditional edges      
    builder.add_edge(START, ANALYZE_QUERY)
    
    # Intent-based branching on the edge from analyze_query
    builder.add_conditional_edges(
        ANALYZE_QUERY, 
        route_by_intent, 
        {
            "complaint_query": RETRIEVE_POLICIES,
            "other_query": SMALLTALK,
        }
    )
    
    builder.add_conditional_edges(
        RETRIEVE_POLICIES,
        route_after_retrieval,
        {
            "match_found": GENERATE,
            "no_match_found": NO_MATCH,
        },
    )

    builder.add_edge(GENERATE, END)
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