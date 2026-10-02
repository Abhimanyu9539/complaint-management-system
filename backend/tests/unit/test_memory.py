"""`rag/memory.py`: what the model sees of the earlier conversation, and when turns are folded."""

from langchain_core.messages import AIMessage, HumanMessage

from cms.config.settings import get_settings
from cms.rag.memory import format_conversation, format_turns, strip_markers, turns_to_fold


def _turns(count: int, answer: str = "an answer") -> list:
    """`count` turns — a human and an AI message each, as `record_turn` writes them."""
    history = []
    for index in range(count):
        history += [HumanMessage(f"question {index}"), AIMessage(f"{answer} {index}")]
    return history


def test_markers_and_the_space_before_them_are_stripped() -> None:
    assert strip_markers("Covered [1]. Replace it [2][4].") == "Covered. Replace it."


def test_turns_are_labelled_by_role() -> None:
    text = format_turns([HumanMessage("my X200 died"), AIMessage("Covered [1].")])
    assert text == "Agent: my X200 died\n\nAssistant: Covered."


def test_a_first_turn_has_no_conversation() -> None:
    assert format_conversation({"query": "q"}) == ""
    assert format_conversation({"query": "q", "chat_history": []}) == ""


def test_the_conversation_is_the_summary_plus_only_the_unsummarized_turns() -> None:
    state = {
        "query": "q",
        "history_summary": "## X200 vacuum — stopped charging",
        "summarized_count": 2,
        "chat_history": _turns(2),
    }

    block = format_conversation(state)

    assert block.startswith("\n<conversation>\n<summary>\n## X200 vacuum")
    assert "question 0" not in block  # folded into the summary
    assert "Agent: question 1" in block
    assert block.endswith("</conversation>\n")


def test_nothing_is_folded_while_the_turns_fit(monkeypatch) -> None:
    monkeypatch.setattr(get_settings(), "memory_recent_turns", 2)
    monkeypatch.setattr(get_settings(), "memory_summary_trigger_tokens", 10_000)

    assert turns_to_fold({"query": "q", "chat_history": _turns(5)}) == []


def test_nothing_is_folded_with_only_the_recent_turns(monkeypatch) -> None:
    """Over the token trigger, but every turn is one of the last `memory_recent_turns`."""
    monkeypatch.setattr(get_settings(), "memory_recent_turns", 2)
    monkeypatch.setattr(get_settings(), "memory_summary_trigger_tokens", 1)

    assert turns_to_fold({"query": "q", "chat_history": _turns(2)}) == []


def test_a_fold_keeps_the_recent_turns_word_for_word(monkeypatch) -> None:
    monkeypatch.setattr(get_settings(), "memory_recent_turns", 2)
    monkeypatch.setattr(get_settings(), "memory_summary_trigger_tokens", 1)
    history = _turns(5)

    fold = turns_to_fold({"query": "q", "chat_history": history})

    assert fold == history[:6]  # turns 0-2 folded, turns 3-4 kept


def test_a_fold_starts_after_what_is_already_summarized(monkeypatch) -> None:
    monkeypatch.setattr(get_settings(), "memory_recent_turns", 1)
    monkeypatch.setattr(get_settings(), "memory_summary_trigger_tokens", 1)
    history = _turns(4)

    fold = turns_to_fold({"query": "q", "chat_history": history, "summarized_count": 4})

    assert fold == history[4:6]
