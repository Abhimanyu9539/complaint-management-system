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


class UnsupportedClaim(_Base):
    """One material claim in a draft that the evidence does not support."""

    claim: str = Field(description="The claim, quoted briefly from the draft.")
    reason: str = Field(description="Why the evidence does not support it, citing [n] where relevant.")


class FactCheckFindings(_Base):
    """The structured output of the claim finder that runs when NeMo's fact check blocks."""

    unsupported_claims: list[UnsupportedClaim] = Field(
        default_factory=list,
        description="Every unsupported or contradicted material claim; empty when there are none.",
    )
