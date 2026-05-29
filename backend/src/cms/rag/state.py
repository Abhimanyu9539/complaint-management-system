"""`GraphState`: the one object every graph node reads from and writes a partial update to"""

from typing import Annotated, TypedDict

from langchain_core.documents import Document
from langchain_core.messages import BaseMessage
from langgraph.graph.message import add_messages

from cms.schemas.generation import Citation
from cms.schemas.query_analysis import Intent, RiskFlag


class _RequiredState(TypedDict):
    query: str


class GraphState(_RequiredState, total=False):
    # --- session ---
    session_id: str
    user_id: str
    # The only slot that accumulates across turns; `record_turn` appends to it
    # and nothing reads it during a run. Every other slot is last-write-wins,
    # which is why `new_turn` exists.
    chat_history: Annotated[list[BaseMessage], add_messages]

    # --- guardrails (input_guard, output_guard) ---
    input_blocked: bool
    guard_reasons: list[str]

    # --- query analysis (analyze_query — this slice) ---
    intent: Intent
    policy_queries: list[str]
    risk_flags: list[RiskFlag]
    requires_lead_review: bool

    # --- retrieval  ---
    policy_hits: list[tuple[Document, float]]  # (chunk, score), best first
    case_hits: list[tuple[Document, float]]  # (chunk, score), best first
    retrieval_attempts: int
    no_match: bool

    # --- generation ---
    draft: str
    citations: list[Citation]
    grounded: bool | None
    regenerated: bool
    message_id: str


def new_turn(query: str, session_id: str, user_id: str) -> GraphState:
    """The graph input for one turn, with every carried-over slot cleared.

    Load-bearing, not hygiene. With a checkpointer the state survives into the
    next turn, and two of these leak badly:

    - a stale `grounded=False` makes `generate` treat a fresh question as a
      retry and feed the *previous* turn's answer into the prompt as
      `<previous_draft>`;
    - a stale `regenerated=True` makes `route_after_output_guard` return
      `still_ungrounded`, killing the retry path for the rest of the thread.

    `intent` is deliberately absent: it is a Literal that `analyze_query` always
    writes before anything reads it, so None would be a type lie. `chat_history`
    is absent too — `record_turn` owns it, and building the message here would
    store the query as the user typed it, before `input_guard` masked its PII.
    """
    return GraphState(
        query=query,
        session_id=session_id,
        user_id=user_id,
        # Correctness: each of these is read before it is written on some path.
        draft="",
        citations=[],
        grounded=None,
        regenerated=False,
        guard_reasons=[],
        message_id="",
        # Defence, and keeps a smalltalk turn from checkpointing the previous
        # complaint's retrieved chunks.
        input_blocked=False,
        policy_queries=[],
        risk_flags=[],
        requires_lead_review=False,
        policy_hits=[],
        case_hits=[],
        no_match=False,
    )
