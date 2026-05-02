"""Graph assembly: analyze the query, then fork on intent.

    START -> analyze_query -+-> retrieve_policies -+-> no_match -> END
                            |                      +-> END
                            +-> smalltalk         -> END
"""

from functools import lru_cache

from langgraph.graph import END, START, StateGraph
from langgraph.graph.state import CompiledStateGraph

from cms.rag.nodes.analyze_query import analyze_query
from cms.rag.nodes.no_match import no_match
from cms.rag.nodes.retrieve_policies import retrieve_policies
from cms.rag.nodes.smalltalk import smalltalk
from cms.rag.state import GraphState

# Node names, so the router and the edges cannot drift apart.
ANALYZE_QUERY = "analyze_query"
RETRIEVE_POLICIES = "retrieve_policies"
SMALLTALK = "smalltalk"
NO_MATCH = "no_match"

COMPLAINT_QUERY = "complaint_query"


def route_by_intent(state: GraphState) -> str:
    """Which branch runs after `analyze_query`.

    Anything that is not a complaint goes to smalltalk — there are no policy
    queries to search with, so retrieval would have nothing to do.

    Kept side-effect free so callers can re-derive the branch from a finished
    state; each node logs its own line anyway.
    """
    return RETRIEVE_POLICIES if state.get("intent") == COMPLAINT_QUERY else SMALLTALK


def route_after_retrieval(state: GraphState) -> str:
    """Which branch runs after `retrieve_policies`.

    Nothing retrieved means nothing to ground an answer in, so we answer
    honestly rather than let a model fill the gap from memory.
    """
    return NO_MATCH if state.get("no_match") else END


def build_graph() -> CompiledStateGraph:
    """Wire the nodes and compile."""
    builder = StateGraph(GraphState)

    builder.add_node(ANALYZE_QUERY, analyze_query)
    builder.add_node(RETRIEVE_POLICIES, retrieve_policies)
    builder.add_node(SMALLTALK, smalltalk)
    builder.add_node(NO_MATCH, no_match)

    builder.add_edge(START, ANALYZE_QUERY)
    builder.add_conditional_edges(
        ANALYZE_QUERY, 
        route_by_intent, 
        [RETRIEVE_POLICIES, SMALLTALK]
    )
    builder.add_conditional_edges(
        RETRIEVE_POLICIES, 
        route_after_retrieval, 
        [NO_MATCH, END]
    )
    builder.add_edge(NO_MATCH, END)
    builder.add_edge(SMALLTALK, END)
    return builder.compile()


@lru_cache
def get_graph() -> CompiledStateGraph:
    """The process-wide compiled graph — compiling is pure setup, so do it once."""
    return build_graph()
