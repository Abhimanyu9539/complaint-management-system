"""`GraphState`: the one object every graph node reads from and writes a partial update to
"""

from typing import TypedDict

from langchain_core.documents import Document
from langchain_core.messages import BaseMessage

from cms.schemas.query_analysis import Intent


class _RequiredState(TypedDict):
    query: str


class GraphState(_RequiredState, total=False):
    # --- session ---
    session_id: str
    user_id: str
    chat_history: list[BaseMessage]

    # --- query analysis (analyze_query — this slice) ---
    intent: Intent
    policy_queries: list[str]

    # --- retrieval  ---
    policy_hits: list[tuple[Document, float]]  # (chunk, score), best first
    retrieval_attempts: int
    no_match: bool

    # --- generation ---
    draft: str
    citations: list[dict]
    grounded: bool | None
    regenerated: bool
