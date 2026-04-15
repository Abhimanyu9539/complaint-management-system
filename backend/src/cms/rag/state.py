"""`GraphState`: the one object every graph node reads from and writes a
partial update to (build.md §0.3.1).

Declared whole now, before most of its nodes exist, per steps.md's own
rationale for doing state first: "every node's signature is 'state in ->
partial state out'; getting the shape right makes nodes independently
testable." Only `analyze_query` writes to it so far — `session_id` through
`regenerated` sit unused until the nodes that own them are built, so the
schema itself doesn't move again as they land.

The retrieval fields are the exception: the chunk-typed ones (`retrieved`,
`graded`) land with the retriever, since their element type is the
retriever's own result shape.

Split into a required base and an optional extension so `query` is the only
field a caller must supply up front — `GraphState(query="...")` is a valid
starting state; everything else accumulates as nodes run.
"""

from typing import TypedDict

from langchain_core.messages import BaseMessage

from cms.schemas.query_analysis import Intent


class _RequiredState(TypedDict):
    query: str


class GraphState(_RequiredState, total=False):
    # --- session (Step 7 wires these; declared now, unused until then) ---
    session_id: str
    user_id: str
    chat_history: list[BaseMessage]

    # --- query analysis (analyze_query — this slice) ---
    intent: Intent
    department: str | None
    dept_confidence: float
    # Each entry is a `DepartmentCandidate.model_dump()`, not the pydantic
    # model itself — GraphState is expected to be checkpoint/serialization
    # friendly (build.md's later persistence phases), and nothing downstream
    # needs more than plain dict access.
    department_candidates: list[dict]
    entities: dict[str, str]
    search_queries: list[str]

    # --- retrieval (retrieve/grade_documents/rewrite_query — later slices) ---
    retrieval_attempts: int
    no_match: bool

    # --- generation (generate/check_groundedness — later slices) ---
    draft: str
    citations: list[dict]
    grounded: bool | None
    regenerated: bool
