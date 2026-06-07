"""Runs the RAG graph for one chat turn and yields it to the browser as SSE events.

Two things make this more than a loop over `astream`:

1. `output_guard` can send an ungrounded draft back to `generate`, so a second
   draft streams right after the first. The browser appends every token it is
   given, so it is told to drop the first one with a `reset` event.
2. `blocked_input`, `no_match` and `add_caveat` set `draft` with no LLM call, so
   nothing streams for them at all — and `add_caveat` prefixes a draft that did.
   The final state is therefore the authority, and the stream is reconciled
   against it before `citations` goes out.

`session_messages` is the other half: the same conversation read back out of the
checkpointer when the browser reopens it.
"""

import json
import logging
import uuid
from collections.abc import AsyncIterator
from typing import Any

from langchain_core.messages import BaseMessage

from cms.config.settings import get_settings
from cms.db.mongo import get_checkpointer
from cms.rag.graph import GENERATE, SMALLTALK, get_graph
from cms.rag.state import new_turn
from cms.schemas.chat import ChatDone, ChatMessageOut
from cms.schemas.generation import Citation

logger = logging.getLogger(__name__)

# The only nodes that write the answer with an LLM. Tokens from the cheap models
# in analyze_query and the guards run through the same stream and are not shown.
ANSWER_NODES = frozenset({GENERATE, SMALLTALK})


def _event(name: str, data: Any) -> dict[str, str]:
    """One SSE record. JSON keeps every payload on a single `data:` line."""
    return {"event": name, "data": json.dumps(data)}


async def stream_turn(
    message: str, session_id: str | None, user_id: str
) -> AsyncIterator[dict[str, str]]:
    """Stream one answer: `token`* -> `citations` -> `done`, or `error`.

    `values` rides alongside `messages` so the final state is in hand when the
    stream ends, without a second graph run.

    `thread_id` is the session id as-is. `user_id` rides in `configurable`, which
    LangGraph copies into the checkpoint metadata — so conversations can be
    attributed once auth lands, without the thread key changing and orphaning
    every session that already exists.
    """
    settings = get_settings()
    session = session_id or str(uuid.uuid4())
    config = {"configurable": {"thread_id": session, "user_id": user_id}}
    streamed = ""
    step: int | None = None
    final: dict[str, Any] = {}

    # One checkpoint at the end of the turn instead of one per super-step. Also
    # means an abandoned stream stores nothing. LangGraph warns if this is set
    # with no checkpointer, hence the gate.
    durability = "exit" if settings.chat_memory_enabled else None

    try:
        async for mode, payload in get_graph().astream(
            new_turn(message, session, user_id),
            config=config,
            stream_mode=["messages", "values"],
            durability=durability,
        ):
            if mode == "values":
                final = payload
                continue

            chunk, meta = payload
            if meta.get("langgraph_node") not in ANSWER_NODES:
                continue

            # A new super-step on an answer node means generate ran again, so
            # everything sent so far belongs to the draft the guard rejected.
            current = meta.get("langgraph_step")
            if step is not None and current != step:
                logger.info("chat: draft regenerated, resetting the stream")
                streamed = ""
                yield _event("reset", {})
            step = current

            text = chunk.content if isinstance(chunk.content, str) else ""
            if text:
                streamed += text
                yield _event("token", text)

        draft = final.get("draft", "")
        if draft != streamed:
            # A node wrote the answer directly, or caveated the one that streamed.
            if streamed:
                yield _event("reset", {})
            yield _event("token", draft)

        citations = [citation.model_dump() for citation in final.get("citations", [])]
        yield _event("citations", citations)
        # `record_turn` mints the id it stored the answer under, so the browser
        # holds the same id the transcript does. Falls back only when memory is
        # off and that node wrote nothing.
        yield _event(
            "done",
            ChatDone(
                message_id=final.get("message_id") or str(uuid.uuid4()),
                session_id=session,
            ).model_dump(),
        )
        logger.info(
            "chat: answered session %s with %d char(s) and %d citation(s)",
            session,
            len(draft),
            len(citations),
        )
    except Exception:
        # The response has already started, so this cannot become a 500 —
        # the browser only ever learns about it through the stream.
        logger.exception("chat: the graph failed for session %s", session)
        yield _event("error", {"message": get_settings().chat_error_message})


def _to_message(message: BaseMessage) -> ChatMessageOut | None:
    """One stored `BaseMessage` as the UI's shape, or None for anything else.

    Citations come back as plain dicts — `record_turn` dumps them on the way in,
    because a pydantic model nested in `additional_kwargs` does not survive the
    checkpointer's round trip.
    """
    role = {"human": "user", "ai": "assistant"}.get(message.type)
    if role is None:
        return None

    extra = message.additional_kwargs
    try:
        citations = [Citation(**citation) for citation in extra.get("citations", [])]
    except Exception:
        # A stored citation that no longer matches the schema must not take the
        # whole transcript down with it.
        logger.exception("chat: could not rebuild citations for message %s", message.id)
        citations = []

    return ChatMessageOut(
        id=str(message.id or uuid.uuid4()),
        role=role,
        content=message.content if isinstance(message.content, str) else str(message.content),
        citations=citations,
        created_at=extra.get("created_at", ""),
    )


async def session_messages(session_id: str, user_id: str) -> list[ChatMessageOut]:
    """Every stored turn of one session, oldest first.

    Reads the checkpointer's latest snapshot rather than a message table: the
    checkpoint *is* the transcript. An unknown session has no snapshot, which
    reads as an empty list.
    """
    config = {"configurable": {"thread_id": session_id, "user_id": user_id}}
    try:
        snapshot = await get_graph().aget_state(config)
    except Exception:
        logger.exception("chat: could not load session %s", session_id)
        raise

    history = snapshot.values.get("chat_history", [])
    messages = [out for out in (_to_message(message) for message in history) if out]
    logger.info("chat: replayed %d message(s) for session %s", len(messages), session_id)
    return messages


async def delete_session(session_id: str) -> None:
    """Remove every stored checkpoint of one session. An unknown id is a no-op."""
    try:
        await get_checkpointer().adelete_thread(session_id)
    except Exception:
        logger.exception("chat: could not delete session %s", session_id)
        raise
    logger.info("chat: deleted session %s", session_id)
