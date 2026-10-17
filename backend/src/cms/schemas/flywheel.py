"""Contracts for the judge that spots a duplicate case."""

from pydantic import BaseModel, ConfigDict, Field


class _Base(BaseModel):
    model_config = ConfigDict(frozen=True)


class CaseComparison(_Base):
    """The judge's verdict on a new case against one past case."""

    same_complaint: bool = Field(description="Both cases are the same kind of complaint.")
    same_resolution: bool = Field(description="Both were resolved with the same remedy and outcome.")
    reason: str = Field(description="One sentence on why.")
