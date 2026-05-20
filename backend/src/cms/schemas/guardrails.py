"""Contracts for the guardrail checks around the graph."""

from pydantic import BaseModel, ConfigDict, Field


class _Base(BaseModel):
    model_config = ConfigDict(frozen=True)


class GuardResult(_Base):
    """One check's verdict.

    `text` is what may go on — the complaint with sensitive data masked, or the
    draft unchanged. `reasons` say why it failed, worded so they can be fed back
    to the model on a regeneration.
    """

    passed: bool
    text: str
    reasons: list[str] = Field(default_factory=list)
