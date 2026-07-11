"""Contracts for incoming email: what n8n posts, and what the API did with it."""

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

# `duplicate` is never stored: the first copy's row already says what happened.
InboundOutcome = Literal["created", "dept_answer", "customer_reply", "ignored", "duplicate"]


class InboundEmailRequest(BaseModel):
    """One email, normalised by n8n. Bounded like `CreateTicketRequest`."""

    model_config = ConfigDict(frozen=True)

    message_id: str = Field(min_length=1, max_length=998)
    from_address: str = Field(min_length=3, max_length=320, description="The From header; a display name is fine.")
    subject: str = Field(default="", max_length=998)
    text: str = Field(default="", max_length=100_000, description="The plain-text body.")
    auto_submitted: str | None = Field(default=None, max_length=100)


class InboundEmailResult(BaseModel):
    model_config = ConfigDict(frozen=True)

    outcome: InboundOutcome
    reason: str | None = None
    ticket_id: str | None = None
    ticket_no: int | None = None
