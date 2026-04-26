"""The response body of OpenRouter's `/rerank` endpoint.

`extra="ignore"` throughout: OpenRouter echoes `document` back when
`return_documents` is set and is free to add fields, none of which we read —
the candidates are already in hand, and `index` maps a result to its original.
"""

from pydantic import BaseModel, ConfigDict, Field


class _Base(BaseModel):
    model_config = ConfigDict(frozen=True, extra="ignore")


class RerankUsage(BaseModel):
    """Token accounting. Optional — reported for cost, never depended on."""

    model_config = ConfigDict(frozen=True, extra="ignore")

    total_tokens: int | None = None


class RerankResult(_Base):
    """One scored candidate. `index` points into the request's `documents`."""

    index: int = Field(ge=0)
    relevance_score: float


class RerankResponse(_Base):
    """One rerank call's results, already sorted best-first by the API."""

    results: list[RerankResult]
    model: str | None = None
    usage: RerankUsage | None = None
