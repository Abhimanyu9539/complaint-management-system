import json
from types import SimpleNamespace

from cms.schemas.generation import Citation
from cms.services import chat_service

CITATION = Citation(
    marker=1, doc_id="p", chunk_id="p1", title="Warranty", section="2.3", snippet="the clause"
)


def _install_graph(monkeypatch, events: list) -> list[dict]:
    """Stub the compiled graph with a scripted `astream`, so no model is called.

    Returns the list the stub records its call kwargs into, so a test can assert
    on the thread config the service built.
    """
    calls: list[dict] = []

    async def astream(graph_input, config=None, stream_mode=None, durability=None):
        calls.append({"input": graph_input, "config": config, "durability": durability})
        for event in events:
            yield event

    monkeypatch.setattr(chat_service, "get_graph", lambda: SimpleNamespace(astream=astream))
    return calls


def _token(text: str, node: str = "generate", step: int = 1) -> tuple:
    """One `messages` record, as LangGraph emits it."""
    return (
        "messages",
        (SimpleNamespace(content=text), {"langgraph_node": node, "langgraph_step": step}),
    )


async def _collect(
    message: str = "my blender shows ERR-22", session_id=None, user_id: str = "anonymous"
) -> list[dict]:
    return [
        {"event": event["event"], "data": json.loads(event["data"])}
        async for event in chat_service.stream_turn(message, session_id, user_id)
    ]


async def test_streams_tokens_then_citations_and_done(monkeypatch) -> None:
    _install_graph(
        monkeypatch,
        [
            _token("Refund "),
            _token("approved."),
            ("values", {"draft": "Refund approved.", "citations": [CITATION]}),
        ],
    )

    events = await _collect()

    assert [event["event"] for event in events] == ["token", "token", "citations", "done"]
    assert "".join(e["data"] for e in events if e["event"] == "token") == "Refund approved."
    assert events[2]["data"][0]["snippet"] == "the clause"


async def test_session_id_is_echoed_when_given_and_minted_when_not(monkeypatch) -> None:
    _install_graph(monkeypatch, [_token("hi"), ("values", {"draft": "hi", "citations": []})])

    kept = await _collect(session_id="session-1")
    minted = await _collect()

    # The UI drops the whole turn if `done` carries no session id.
    assert kept[-1]["data"]["session_id"] == "session-1"
    assert minted[-1]["data"]["session_id"]


async def test_tokens_from_other_nodes_are_not_shown(monkeypatch) -> None:
    _install_graph(
        monkeypatch,
        [
            _token("complaint_query", node="analyze_query"),
            _token("The warranty covers this."),
            ("values", {"draft": "The warranty covers this.", "citations": []}),
        ],
    )

    events = await _collect()

    assert [event["data"] for event in events if event["event"] == "token"] == [
        "The warranty covers this."
    ]


async def test_regenerated_draft_resets_the_stream(monkeypatch) -> None:
    # A second `generate` run lands on a later super-step.
    _install_graph(
        monkeypatch,
        [
            _token("ungrounded draft", step=4),
            _token("revised draft", step=6),
            ("values", {"draft": "revised draft", "citations": []}),
        ],
    )

    events = await _collect()

    # Without the reset the browser would show both drafts run together.
    assert [event["event"] for event in events] == ["token", "reset", "token", "citations", "done"]
    assert events[2]["data"] == "revised draft"


async def test_draft_written_without_an_llm_is_sent_whole(monkeypatch) -> None:
    # no_match, blocked_input: `draft` is set directly, so nothing ever streams.
    _install_graph(monkeypatch, [("values", {"draft": "no match reply", "citations": []})])

    events = await _collect()

    assert [event["event"] for event in events] == ["token", "citations", "done"]
    assert events[0]["data"] == "no match reply"


async def test_caveated_draft_replaces_what_streamed(monkeypatch) -> None:
    _install_graph(
        monkeypatch,
        [
            _token("risky draft"),
            ("values", {"draft": "CAUTION\nrisky draft", "citations": []}),
        ],
    )

    events = await _collect()

    assert [event["event"] for event in events] == ["token", "reset", "token", "citations", "done"]
    assert events[2]["data"] == "CAUTION\nrisky draft"


async def test_graph_failure_becomes_an_error_event(monkeypatch) -> None:
    async def astream(_input, stream_mode=None):
        raise RuntimeError("openrouter is down")
        yield  # unreachable; makes this an async generator

    monkeypatch.setattr(chat_service, "get_graph", lambda: SimpleNamespace(astream=astream))

    events = await _collect()

    # The response has already started, so the failure has to travel in the stream.
    assert [event["event"] for event in events] == ["error"]
    assert events[0]["data"]["message"]


async def test_the_graph_is_run_on_a_thread_keyed_by_session(monkeypatch) -> None:
    """`thread_id` is the session id as-is; `user_id` rides alongside it so
    LangGraph copies it into the checkpoint metadata."""
    calls = _install_graph(monkeypatch, [("values", {"draft": "d", "citations": []})])
    await _collect(session_id="session-7", user_id="user-9")

    configurable = calls[0]["config"]["configurable"]
    assert configurable["thread_id"] == "session-7"
    assert configurable["user_id"] == "user-9"
    # One checkpoint per turn rather than one per super-step.
    assert calls[0]["durability"] == "exit"


async def test_the_turn_starts_from_a_cleared_state(monkeypatch) -> None:
    """Without this the checkpointer hands the next turn the previous verdict."""
    calls = _install_graph(monkeypatch, [("values", {"draft": "d", "citations": []})])
    await _collect()

    graph_input = calls[0]["input"]
    assert graph_input["grounded"] is None
    assert graph_input["regenerated"] is False
    assert graph_input["draft"] == ""


async def test_durability_is_off_when_chat_memory_is_disabled(monkeypatch) -> None:
    """LangGraph warns if durability is set with no checkpointer behind it."""
    calls = _install_graph(monkeypatch, [("values", {"draft": "d", "citations": []})])
    settings = chat_service.get_settings()
    monkeypatch.setattr(
        chat_service, "get_settings", lambda: settings.model_copy(update={"chat_memory_enabled": False})
    )
    await _collect()

    assert calls[0]["durability"] is None


async def test_done_carries_the_id_the_turn_was_stored_under(monkeypatch) -> None:
    _install_graph(
        monkeypatch,
        [("values", {"draft": "d", "citations": [], "message_id": "stored-id"})],
    )
    events = await _collect()

    assert events[-1]["data"]["message_id"] == "stored-id"


async def test_lookup_answers_stream(monkeypatch) -> None:
    _install_graph(
        monkeypatch,
        [
            _token("- A duplicate charge was refunded ", node="lookup_generate"),
            _token("[1].", node="lookup_generate"),
            ("values", {"draft": "- A duplicate charge was refunded [1].", "citations": []}),
        ],
    )

    events = await _collect("cases where a refund was issued")

    # Streamed token by token — no reset and no whole-draft resend.
    assert [event["event"] for event in events] == ["token", "token", "citations", "done"]
