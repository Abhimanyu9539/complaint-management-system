"""Contracts for the chat endpoint: the request in, the `done` event and replayed messages out."""

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from cms.schemas.generation import Citation


class _Base(BaseModel):
    model_config = ConfigDict(frozen=True)


class ChatRequest(_Base):
    """One turn from the chat UI.

    `min_length` is 1, not `settings.query_min_chars`: the input guard already
    enforces the 10-character floor, and it does so by answering with
    `blocked_input_message` — a readable reply in the chat window. Rejecting the
    same input here would surface as a bare 422 instead.

    `session_id` is whatever the client last received; the server mints one when
    it is absent. Nothing is persisted against it today.
    """

    message: str = Field(min_length=1, max_length=8000)
    session_id: str | None = Field(default=None, max_length=64)


class ChatDone(_Base):
    """The stream's final event, once the graph has finished.

    `session_id` is not optional: the UI drops the whole turn without it.
    `langsmith_run_id` is the hook feedback will attach to — always None until
    there is a feedback endpoint to send it to.
    """

    message_id: str
    session_id: str
    langsmith_run_id: str | None = None


class ChatMessageOut(_Base):
    """One stored message, replayed from the checkpointer when a session reopens.

    `created_at` is a string because it is read back out of the message's
    `additional_kwargs`, where it was written as an ISO timestamp — there is no
    column to coerce it.
    """

    id: str
    role: Literal["user", "assistant"]
    content: str
    citations: list[Citation] = Field(default_factory=list)
    created_at: str
