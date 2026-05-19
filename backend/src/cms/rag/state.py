"""`GraphState`: the one object every graph node reads from and writes a partial update to
"""

from typing import TypedDict

from langchain_core.documents import Document
from langchain_core.messages import BaseMessage

from cms.schemas.generation import Citation
from cms.schemas.query_analysis import Intent, RiskFlag


class _RequiredState(TypedDict):
    query: str


class GraphState(_RequiredState, total=False):
    # --- session ---
    session_id: str
    user_id: str
    chat_history: list[BaseMessage]

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
