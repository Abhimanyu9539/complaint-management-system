"""`contextualize_query`: a follow-up becomes a standalone question; the typed text is kept."""

from langchain_core.messages import AIMessage, HumanMessage
from langchain_core.runnables import RunnableLambda

from cms.rag.nodes import contextualize_query as contextualize_module

HISTORY = [
    HumanMessage("X200 vacuum stopped charging after 3 months, 12-month warranty"),
    AIMessage("Covered as a defect [1]."),
]


class _FakeMessage:
    def __init__(self, content: str) -> None:
        self.content = content


def _install_model_stub(monkeypatch, reply: str | Exception) -> list[str]:
    """Replace only the chat model, so the real prompt template still renders."""
    prompts: list[str] = []

    def fake_model(prompt_value) -> _FakeMessage:
        prompts.append(prompt_value.to_string())
        if isinstance(reply, Exception):
            raise reply
        return _FakeMessage(reply)

    monkeypatch.setattr(
        contextualize_module, "get_chat_model", lambda model: RunnableLambda(fake_model)
    )
    return prompts


async def test_a_first_turn_is_left_alone_without_a_model_call(monkeypatch) -> None:
    prompts = _install_model_stub(monkeypatch, "should not be used")

    update = await contextualize_module.contextualize_query({"query": "my X200 died"})

    assert update == {"user_message": "my X200 died"}
    assert prompts == []


async def test_a_follow_up_is_rewritten_and_the_typed_text_kept(monkeypatch) -> None:
    standalone = "The customer's X200 stopped charging. What if it is past 12 months?"
    prompts = _install_model_stub(monkeypatch, f"  {standalone}\n")

    update = await contextualize_module.contextualize_query(
        {"query": "what if it's past 12 months?", "chat_history": HISTORY}
    )

    assert update == {"query": standalone, "user_message": "what if it's past 12 months?"}
    assert "Agent: X200 vacuum stopped charging" in prompts[0]
    assert "<message>\nwhat if it's past 12 months?\n</message>" in prompts[0]


async def test_a_failed_rewrite_keeps_the_message_as_typed(monkeypatch) -> None:
    _install_model_stub(monkeypatch, RuntimeError("openrouter down"))

    update = await contextualize_module.contextualize_query(
        {"query": "what if it's past 12 months?", "chat_history": HISTORY}
    )

    assert update == {"user_message": "what if it's past 12 months?"}


async def test_an_empty_rewrite_falls_back_to_the_message(monkeypatch) -> None:
    _install_model_stub(monkeypatch, "   ")

    update = await contextualize_module.contextualize_query(
        {"query": "and then?", "chat_history": HISTORY}
    )

    assert update["query"] == "and then?"
