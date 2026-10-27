"""Chat memory: the Mongo checkpointer and the session summary."""

from pydantic import BaseModel


class ChatSettings(BaseModel):
    # --- Mongo / chat memory ---
    # Mongo backs the LangGraph checkpointer, which is where a conversation is stored.
    # 27018 is the compose file's host port — see the note there about a native
    # mongod shadowing 27017.
    mongo_url: str = "mongodb://localhost:27018"
    mongo_db_name: str = "cms_chat"
    # Caps how long a down Mongo stalls a request. pymongo's own default is 30s,
    # which is long enough to look like a hang.
    mongo_timeout_ms: int = 5000
    # Kill switch: False compiles the graph with no checkpointer, which is the
    # pre-Mongo behaviour — chat works, nothing is stored.
    chat_memory_enabled: bool = True
    # Session memory: the model sees a running summary plus every turn not yet in
    # it. Once those turns pass the trigger, all but the last `memory_recent_turns`
    # are folded into the summary. A turn measures ~240 tokens (answer median ~180,
    # max 331; agent message ~57 — 2026-10-03 generate eval), so the first summary
    # lands around turn 25 and then roughly every 19 turns.
    memory_recent_turns: int = 6
    memory_summary_trigger_tokens: int = 6000
    memory_summary_max_words: int = 600
    # `input_guard` only masks PII on the *allowed* path; a blocked message is
    # still raw, and blocked is exactly when it holds a credential. Stored in its
    # place so a replayed transcript never shows what was rejected.
    blocked_message_placeholder: str = "[message withheld]"
