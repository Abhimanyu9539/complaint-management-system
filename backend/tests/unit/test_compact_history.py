"""`compact_history`: fold old turns into the summary once they no longer fit, and never fail the turn."""

from langchain_core.messages import AIMessage, HumanMessage
from langchain_core.runnables import RunnableLambda

from cms.config.settings import get_settings
from cms.rag.nodes import compact_history as compact_module

SUMMARY = "## X200 vacuum — stopped charging\n- Facts: bought 3 months ago"


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

    monkeypatch.setattr(compact_module, "get_chat_model", lambda model: RunnableLambda(fake_model))
    return prompts


def _state(turns: int, **extra) -> dict:
    history = []
    for index in range(turns):
        history += [HumanMessage(f"question {index}"), AIMessage(f"answer {index} [1]")]
    return {"query": "q", "chat_history": history, **extra}


def _fold_everything_but_one_turn(monkeypatch) -> None:
    monkeypatch.setattr(get_settings(), "memory_recent_turns", 1)
    monkeypatch.setattr(get_settings(), "memory_summary_trigger_tokens", 1)


async def test_turns_that_fit_cost_no_model_call(monkeypatch) -> None:
    prompts = _install_model_stub(monkeypatch, SUMMARY)

    update = await compact_module.compact_history(_state(3))

    assert update == {}
    assert prompts == []


async def test_a_fold_writes_the_summary_and_how_far_it_reaches(monkeypatch) -> None:
    _fold_everything_but_one_turn(monkeypatch)
    prompts = _install_model_stub(monkeypatch, f"{SUMMARY}\n")

    update = await compact_module.compact_history(_state(3))

    assert update == {"history_summary": SUMMARY, "summarized_count": 4}
    # Only the folded turns go in, without their markers; the last turn stays out.
    assert "Assistant: answer 1\n</turns>" in prompts[0]
    assert "question 2" not in prompts[0]
    assert "<summary>\n(none yet)\n</summary>" in prompts[0]


async def test_a_second_fold_merges_into_the_existing_summary(monkeypatch) -> None:
    _fold_everything_but_one_turn(monkeypatch)
    prompts = _install_model_stub(monkeypatch, SUMMARY)

    update = await compact_module.compact_history(
        _state(4, history_summary="## Older complaint", summarized_count=4)
    )

    assert update["summarized_count"] == 6
    assert "<summary>\n## Older complaint\n</summary>" in prompts[0]
    assert "question 1" not in prompts[0]  # already in the summary


async def test_a_failed_fold_keeps_the_old_summary(monkeypatch) -> None:
    _fold_everything_but_one_turn(monkeypatch)
    _install_model_stub(monkeypatch, RuntimeError("openrouter down"))

    assert await compact_module.compact_history(_state(3)) == {}


async def test_an_empty_summary_is_not_stored(monkeypatch) -> None:
    """Advancing `summarized_count` with no summary would drop those turns from memory."""
    _fold_everything_but_one_turn(monkeypatch)
    _install_model_stub(monkeypatch, "  ")

    assert await compact_module.compact_history(_state(3)) == {}
