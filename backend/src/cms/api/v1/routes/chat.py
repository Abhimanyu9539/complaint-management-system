"""The chat endpoint: one complaint question in, one streamed answer out, plus replay.

Server-sent events rather than a plain JSON response because the graph takes
seconds to answer — guards, two retrievals and a generation — and a support
agent watching an answer appear is waiting far better than one watching a
spinner. `EventSourceResponse` also pings on its own, which keeps the
connection alive across the silent stretch before the first token.

Turns are stored in Mongo by the graph's checkpointer, keyed by the signed-in
user and `session_id` together, so one agent can never read or extend another's
conversation. Not in Supabase: `chat_sessions` and `messages` are RLS'd to
`auth.uid()` and this API holds the service-role key, which bypasses RLS.
"""

import logging

from fastapi import APIRouter, Depends, Path
from sse_starlette.sse import EventSourceResponse

from cms.api.deps import get_current_user
from cms.db.mongo import get_checkpointer
from cms.schemas.auth import CurrentUser
from cms.schemas.chat import ChatMessageOut, ChatRequest
from cms.services.chat_service import delete_session, session_messages, stream_turn

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/chat", tags=["chat"])

@router.post("")
async def chat(
    payload: ChatRequest,
    user: CurrentUser = Depends(get_current_user),
) -> EventSourceResponse:
    """Answer one turn as an SSE stream of `token`, `citations` and `done`.

    Always 200: once the stream is open, a failure is an `error` event rather
    than a status code, so the handler itself has nothing to catch.
    """
    logger.info("chat: %d char(s) in for session %s", len(payload.message), payload.session_id)
    return EventSourceResponse(
        stream_turn(payload.message.strip(), payload.session_id, user.id)
    )

@router.get("/sessions/{session_id}/messages")
async def session_transcript(
    session_id: str = Path(max_length=64),
    user: CurrentUser = Depends(get_current_user),
) -> list[ChatMessageOut]:
    """Replay one of the caller's stored conversations, so a reload restores it.

    An unknown session is an empty list, not a 404 — the client cannot tell the
    difference between never-existed, expired and someone else's, and need not.
    """
    if get_checkpointer() is None:
        logger.warning("chat: transcript requested for %s but chat memory is off", session_id)
        return []
    return await session_messages(session_id, user.id)

@router.delete("/sessions/{session_id}", status_code=204)
async def delete_chat_session(
    session_id: str = Path(max_length=64),
    user: CurrentUser = Depends(get_current_user),
) -> None:
    """Delete one of the caller's conversations. Idempotent: an unknown session is still a 204."""
    if get_checkpointer() is None:
        logger.warning("chat: delete requested for %s but chat memory is off", session_id)
        return
    await delete_session(session_id, user.id)
