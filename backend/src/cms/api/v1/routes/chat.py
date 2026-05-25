"""The chat endpoint: one complaint question in, one streamed answer out.

Server-sent events rather than a plain JSON response because the graph takes
seconds to answer — guards, two retrievals and a generation — and a support
agent watching an answer appear is waiting far better than one watching a
spinner. `EventSourceResponse` also pings on its own, which keeps the
connection alive across the silent stretch before the first token.

Nothing is persisted: `session_id` is minted and echoed so the UI can group a
conversation, but there is no `chat_sessions` or `messages` write behind it.
That waits on auth — both tables are RLS'd to `auth.uid()`, and this API holds
the service-role key, which bypasses RLS entirely. See the warning in
`tickets.py`; it applies here too.
"""

import logging

from fastapi import APIRouter
from sse_starlette.sse import EventSourceResponse

from cms.schemas.chat import ChatRequest
from cms.services.chat_service import stream_turn

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/chat", tags=["chat"])


@router.post("")
async def chat(payload: ChatRequest) -> EventSourceResponse:
    """Answer one turn as an SSE stream of `token`, `citations` and `done`.

    Always 200: once the stream is open, a failure is an `error` event rather
    than a status code, so the handler itself has nothing to catch.
    """
    logger.info("chat: %d char(s) in for session %s", len(payload.message), payload.session_id)
    return EventSourceResponse(stream_turn(payload.message.strip(), payload.session_id))
