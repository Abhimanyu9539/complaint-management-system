"""The structured output of the `analyze_query` graph node."""

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

Intent = Literal["complaint_query", "knowledge_lookup", "smalltalk_or_meta"]

# Which corpus a knowledge lookup searches.
LookupTarget = Literal["policies", "cases", "both"]

# Tickets a lead reviews before anything is sent (ai §4).
RiskFlag = Literal["legal", "safety", "recall", "vulnerable", "above_authority"]


class _Base(BaseModel):
    model_config = ConfigDict(frozen=True)


class QueryAnalysis(_Base):
    """One `analyze_query` call: the intent, plus the policy-worded queries to retrieve with."""

    intent: Intent
    policy_queries: list[str] = Field(
        default_factory=list,
        max_length=3,
        description=(
            "2-3 policy-worded retrieval queries; empty for smalltalk_or_meta and for "
            "a knowledge_lookup that searches cases only."
        ),
    )
    lookup_target: LookupTarget = Field(
        default="both",
        description="Which corpus a knowledge_lookup searches. Ignored for the other intents.",
    )
    risk_flags: list[RiskFlag] = Field(
        default_factory=list,
        description="Every risk the complaint raises; empty when none apply.",
    )
