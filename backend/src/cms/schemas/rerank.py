"""The response body of OpenRouter's `/rerank`. Extra fields are ignored."""

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
