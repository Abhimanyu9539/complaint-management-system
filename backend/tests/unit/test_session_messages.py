"""Replaying a stored conversation out of the checkpointer."""

from types import SimpleNamespace

from langchain_core.messages import AIMessage, HumanMessage, SystemMessage

from cms.services import chat_service

CITATION_DICT = {
    "marker": 1,
    "doc_id": "p",
    "chunk_id": "p1",
    "title": "Warranty",
    "section": "2.3",
    "snippet": "the clause",
}


def _install_state(monkeypatch, history: list) -> list[dict]:
    """Stub the graph with a scripted `aget_state`, so no Mongo is needed."""
    calls: list[dict] = []

    async def aget_state(config):
        calls.append(config)
        return SimpleNamespace(values={"chat_history": history})

    monkeypatch.setattr(chat_service, "get_graph", lambda: SimpleNamespace(aget_state=aget_state))
    return calls


async def test_messages_are_mapped_to_the_ui_shape(monkeypatch) -> None:
    _install_state(
        monkeypatch,
        [
            HumanMessage(content="my blender shows ERR-22", additional_kwargs={"created_at": "T1"}),
            AIMessage(
                content="Refund approved.",
                id="m-1",
                additional_kwargs={"citations": [CITATION_DICT], "created_at": "T2"},
            ),
        ],
    )
    messages = await chat_service.session_messages("s-1", "anonymous")

    assert [m.role for m in messages] == ["user", "assistant"]
    assert messages[1].id == "m-1"
    assert messages[1].created_at == "T2"
    assert messages[1].citations[0].title == "Warranty"
    assert messages[0].citations == []


async def test_the_thread_is_keyed_on_the_session_id_alone(monkeypatch) -> None:
    """`user_id` rides in configurable for metadata; it is not part of the key."""
    calls = _install_state(monkeypatch, [])
    await chat_service.session_messages("s-1", "someone")

    assert calls[0]["configurable"]["thread_id"] == "s-1"
    assert calls[0]["configurable"]["user_id"] == "someone"


async def test_an_unknown_session_is_an_empty_list(monkeypatch) -> None:
    _install_state(monkeypatch, [])
    assert await chat_service.session_messages("nope", "anonymous") == []


async def test_non_conversation_messages_are_skipped(monkeypatch) -> None:
    """Only human and ai turns are part of the transcript."""
    _install_state(monkeypatch, [SystemMessage(content="internal"), HumanMessage(content="hi")])
    messages = await chat_service.session_messages("s-1", "anonymous")

    assert [m.role for m in messages] == ["user"]


async def test_an_unreadable_citation_does_not_lose_the_message(monkeypatch) -> None:
    _install_state(
        monkeypatch,
        [AIMessage(content="an answer", id="m-2", additional_kwargs={"citations": [{"bad": 1}]})],
    )
    messages = await chat_service.session_messages("s-1", "anonymous")

    assert messages[0].content == "an answer"
    assert messages[0].citations == []
