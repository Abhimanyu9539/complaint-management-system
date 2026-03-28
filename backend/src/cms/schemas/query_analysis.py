"""The structured output of the `analyze_query` graph node.

The codebase's first LLM-facing contract, so it follows `schemas/admin.py`'s
and `schemas/tickets.py`'s conventions: `_Base` with `frozen=True`, `Literal`
over `Enum` for closed vocabularies, `Field(description=...)` on anything a
reader (or the LLM's tool-call schema) wouldn't otherwise infer.

build.md's `GraphState` sketch has a single `department`/`dept_confidence`
pair, but the retrieve node needs to "widen to top-2 departments" on low
confidence — impossible from a single label. `department_candidates` is the
resolution: the LLM ranks up to 3 candidates, and `department`/
`dept_confidence` below are a read-only view of the top one, kept for
`GraphState` callers that only want the common case.
"""

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

Intent = Literal["complaint_query", "followup", "smalltalk_or_meta"]


class _Base(BaseModel):
    model_config = ConfigDict(frozen=True)


class DepartmentCandidate(_Base):
    """One department guess. `department` is one of the 12 slugs in `departments`."""

    department: str
    confidence: float = Field(ge=0.0, le=1.0)


class QueryAnalysis(_Base):
    """One `analyze_query` call's output: intent, department guesses, entities,
    and rewritten search queries — one structured-output call, no parsing.
    """

    intent: Intent
    department_candidates: list[DepartmentCandidate] = Field(
        min_length=1,
        max_length=3,
        description="Department guesses ranked most-to-least likely.",
    )
    entities: dict[str, str] = Field(
        default_factory=dict,
        description="order_no, product, error_code, etc. — whatever the query names.",
    )
    search_queries: list[str] = Field(
        default_factory=list,
        max_length=3,
        description="1-3 rewritten queries for retrieval; empty for smalltalk_or_meta.",
    )

    @model_validator(mode="after")
    def _sorted_by_confidence(self) -> "QueryAnalysis":
        # Defensive: the LLM is asked to rank these, but nothing guarantees it
        # did — every reader of `department_candidates[0]` depends on this.
        self.department_candidates.sort(key=lambda c: c.confidence, reverse=True)
        return self

    @property
    def department(self) -> str | None:
        """The top-ranked department, or `None` if the model produced none.

        A plain `@property`, not `@computed_field`: this must not appear in
        the JSON schema `.with_structured_output()` sends to OpenAI — the
        model fills in `department_candidates` only, this is a view over it,
        not something the model should extrapolate itself.
        """
        return self.department_candidates[0].department if self.department_candidates else None

    @property
    def dept_confidence(self) -> float:
        """The top-ranked department's confidence, or `0.0` if there is none."""
        return self.department_candidates[0].confidence if self.department_candidates else 0.0
