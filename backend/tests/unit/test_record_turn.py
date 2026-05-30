"""What `record_turn` stores, and what it deliberately does not."""

from cms.config.settings import get_settings
from cms.rag.nodes.record_turn import record_turn
from cms.schemas.generation import Citation

CITATION = Citation(
    marker=1, doc_id="p", chunk_id="p1", title="Warranty", section="2.3", snippet="the clause"
)


async def test_stores_both_messages_with_the_answer_id() -> None:
    update = await record_turn(
        {"query": "my blender shows ERR-22", "draft": "Refund approved.", "citations": [CITATION]}
    )
    human, ai = update["chat_history"]

    assert human.content == "my blender shows ERR-22"
    assert ai.content == "Refund approved."
    # The browser is handed this id in the `done` event, so it must be the
    # assistant message's own id.
    assert ai.id == update["message_id"]
    assert human.additional_kwargs["created_at"]


async def test_citations_are_stored_as_plain_dicts() -> None:
    """A pydantic model nested in `additional_kwargs` does not survive the
    checkpointer's round trip — the message's own `model_dump()` flattens it."""
    update = await record_turn({"query": "q", "draft": "d", "citations": [CITATION]})
    stored = update["chat_history"][1].additional_kwargs["citations"]

    assert isinstance(stored[0], dict)
    assert stored[0]["title"] == "Warranty"


async def test_blocked_input_is_withheld_rather_than_stored() -> None:
    """`input_guard` never masks `query` on the blocked path, and blocked is
    exactly when the text holds something worth withholding."""
    update = await record_turn(
        {"query": "my card is 4111 1111 1111 1111", "draft": "blocked note", "input_blocked": True}
    )
    human = update["chat_history"][0]

    assert human.content == get_settings().blocked_message_placeholder
    assert "4111" not in human.content


async def test_an_allowed_query_is_stored_as_the_guard_left_it() -> None:
    """On the allowed path `query` is already the masked text, so it is stored as-is."""
    update = await record_turn({"query": "my card is <CREDIT_CARD>", "draft": "d"})
    assert update["chat_history"][0].content == "my card is <CREDIT_CARD>"


async def test_retrieved_chunks_are_cleared() -> None:
    update = await record_turn({"query": "q", "draft": "d"})
    assert update["policy_hits"] == []
    assert update["case_hits"] == []
