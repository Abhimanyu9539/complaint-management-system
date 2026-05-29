"""Terminal node: append the finished turn to `chat_history` so the checkpointer stores it.

Runs on every path out of the graph, including the blocked and no-match ones —
whatever the user saw is what gets stored.
"""

import logging
import uuid

from langchain_core.messages import AIMessage, HumanMessage
from langsmith import traceable

from cms.config.settings import get_settings
from cms.db.repositories import utc_now_iso
from cms.rag.state import GraphState

logger = logging.getLogger(__name__)


def _user_text(state: GraphState) -> str:
    """What to store as the user's message.

    `input_guard` replaces `query` with the Presidio-masked text on the allowed
    path, so reading it here is what keeps card numbers and the like out of
    Mongo. On the blocked path it never rewrites `query`, and blocked is exactly
    when the text holds something worth withholding — so that one is replaced.
    """
    if state.get("input_blocked"):
        return get_settings().blocked_message_placeholder
    return state["query"]


@traceable(name="record_turn")
async def record_turn(state: GraphState) -> dict:
    """The graph node: both messages of this turn, plus the id the browser gets.

    Citations are dumped to plain dicts: a pydantic model nested in
    `additional_kwargs` does not survive the checkpointer's round trip — the
    message's own `model_dump()` flattens it before the serializer sees it.

    Retrieved chunks are cleared here so the turn's one checkpoint does not
    carry ~20 policy `Document`s that nothing will read again.
    """
    message_id = str(uuid.uuid4())
    now = utc_now_iso()
    citations = [citation.model_dump() for citation in state.get("citations", [])]
    draft = state.get("draft", "")

    logger.info(
        "record_turn: storing turn %s (%d char(s), %d citation(s))",
        message_id,
        len(draft),
        len(citations),
    )
    return {
        "message_id": message_id,
        "chat_history": [
            HumanMessage(content=_user_text(state), additional_kwargs={"created_at": now}),
            AIMessage(
                content=draft,
                id=message_id,
                additional_kwargs={"citations": citations, "created_at": now},
            ),
        ],
        "policy_hits": [],
        "case_hits": [],
    }
