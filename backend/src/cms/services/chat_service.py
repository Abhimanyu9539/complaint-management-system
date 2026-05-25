"""Runs the RAG graph for one chat turn and yields it to the browser as SSE events.

Two things make this more than a loop over `astream`:

1. `output_guard` can send an ungrounded draft back to `generate`, so a second
   draft streams right after the first. The browser appends every token it is
   given, so it is told to drop the first one with a `reset` event.
2. `blocked_input`, `no_match` and `add_caveat` set `draft` with no LLM call, so
   nothing streams for them at all — and `add_caveat` prefixes a draft that did.
   The final state is therefore the authority, and the stream is reconciled
   against it before `citations` goes out.
"""

import json
import logging
import uuid
from collections.abc import AsyncIterator
from typing import Any

from cms.config.settings import get_settings
from cms.rag.graph import GENERATE, SMALLTALK, get_graph
from cms.schemas.chat import ChatDone

logger = logging.getLogger(__name__)

# The only nodes that write the answer with an LLM. Tokens from the cheap models
# in analyze_query and the guards run through the same stream and are not shown.
ANSWER_NODES = frozenset({GENERATE, SMALLTALK})


def _event(name: str, data: Any) -> dict[str, str]:
    """One SSE record. JSON keeps every payload on a single `data:` line."""
    return {"event": name, "data": json.dumps(data)}


async def stream_turn(message: str, session_id: str | None) -> AsyncIterator[dict[str, str]]:
    """Stream one answer: `token`* -> `citations` -> `done`, or `error`.

    `values` rides alongside `messages` so the final state is in hand when the
    stream ends, without a second graph run.
    """
    session = session_id or str(uuid.uuid4())
    streamed = ""
    step: int | None = None
    final: dict[str, Any] = {}

    try:
        async for mode, payload in get_graph().astream(
            {"query": message}, stream_mode=["messages", "values"]
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
        yield _event(
            "done",
            ChatDone(message_id=str(uuid.uuid4()), session_id=session).model_dump(),
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
