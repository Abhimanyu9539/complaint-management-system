"""Contracts for the daily minting job, and the judge that spots a duplicate case."""

from datetime import date
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

# `duplicate`: a past case has the same complaint and resolution. `skipped`: not ready to mint.
MintOutcome = Literal["minted", "duplicate", "skipped"]


class _Base(BaseModel):
    model_config = ConfigDict(frozen=True)


class FlywheelCandidates(_Base):
    """The tickets resolved on one IST day, oldest first."""

    day: date
    ticket_ids: list[str]


class MintResult(_Base):
    ticket_id: str
    outcome: MintOutcome
    case_id: str | None = None
    similar_case_id: str | None = None
    reason: str | None = None


class CaseComparison(_Base):
    """The judge's verdict on a new case against one past case."""

    same_complaint: bool = Field(description="Both cases are the same kind of complaint.")
    same_resolution: bool = Field(description="Both were resolved with the same remedy and outcome.")
    reason: str = Field(description="One sentence on why.")
