"""Session memory: a running summary of the folded turns, plus every turn not yet in it. No LLM call."""

import logging
import re

from langchain_core.messages import BaseMessage

from cms.config.settings import get_settings
from cms.ingestion.transform.chunker import count_tokens
from cms.rag.context import MARKER_PATTERN
from cms.rag.state import GraphState

logger = logging.getLogger(__name__)

ROLES = {"human": "Agent", "ai": "Assistant"}

# A marker plus the space before it, so "covered [1]." becomes "covered.".
_MARKER_WITH_SPACE = re.compile(r"\s*" + MARKER_PATTERN.pattern)


def strip_markers(text: str) -> str:
    """Drop `[n]` citation markers: they pointed at that turn's sources, not this one's."""
    return _MARKER_WITH_SPACE.sub("", text).strip()


def unsummarized(state: GraphState) -> list[BaseMessage]:
    """The messages not yet folded into the summary, oldest first."""
    return state.get("chat_history", [])[state.get("summarized_count", 0):]


def format_turns(messages: list[BaseMessage]) -> str:
    """One `Agent:` / `Assistant:` paragraph per message, markers stripped."""
    lines = []
    for message in messages:
        role = ROLES.get(message.type)
        if role is None:
            continue
        content = message.content if isinstance(message.content, str) else str(message.content)
        lines.append(f"{role}: {strip_markers(content)}")
    return "\n\n".join(lines)


def format_conversation(state: GraphState) -> str:
    """The `<conversation>` block for a prompt, or "" on a session's first turn."""
    summary = state.get("history_summary", "")
    turns = format_turns(unsummarized(state))
    if not summary and not turns:
        return ""

    parts = [f"<summary>\n{summary}\n</summary>"] if summary else []
    if turns:
        parts.append(turns)
    body = "\n\n".join(parts)
    return f"\n<conversation>\n{body}\n</conversation>\n"


def turns_to_fold(state: GraphState) -> list[BaseMessage]:
    """The oldest unsummarized messages to fold into the summary, or [] while they still fit.

    Folds only once the unsummarized turns pass the token trigger, and always
    keeps the last `memory_recent_turns` turns word for word. A turn is two
    messages — `record_turn` always writes a pair. `count_tokens` returns 0 on a
    tokenizer failure, so a broken tokenizer means no fold, not a failed turn.
    """
    settings = get_settings()
    pending = unsummarized(state)
    keep = 2 * settings.memory_recent_turns
    if len(pending) <= keep:
        return []

    tokens = count_tokens(format_turns(pending))
    if tokens <= settings.memory_summary_trigger_tokens:
        return []

    logger.info(
        "memory: %d unsummarized message(s) at ~%d tokens, folding %d",
        len(pending),
        tokens,
        len(pending) - keep,
    )
    return pending[: len(pending) - keep]
