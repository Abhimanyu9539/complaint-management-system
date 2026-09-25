from langchain_core.documents import Document
from langchain_core.runnables import RunnableLambda

from cms.rag.nodes import lookup_generate as lookup_module


class _FakeMessage:
    def __init__(self, content: str) -> None:
        self.content = content


def _install_model_stub(monkeypatch, reply: str) -> list[str]:
    """Replace only the chat model, so the real `lookup/v1` template still renders."""
    prompts: list[str] = []

    def fake_model(prompt_value) -> _FakeMessage:
        prompts.append(prompt_value.to_string())
        return _FakeMessage(reply)

    monkeypatch.setattr(lookup_module, "get_chat_model", lambda model: RunnableLambda(fake_model))
    return prompts


def _policy_hit() -> tuple[Document, float]:
    return (
        Document(
            page_content="Billing > 1.3 Duplicates\n\nDuplicate charges are refunded.",
            metadata={"doc_id": "pol-1", "chunk_id": "p1", "title": "Billing Policy"},
        ),
        0.9,
    )


def _case_hit(chunk_id: str) -> tuple[Document, float]:
    return (
        Document(
            page_content="COMPLAINT:\ncharged twice\n\nRESOLUTION:\nduplicate refunded",
            metadata={"doc_id": f"case-{chunk_id}", "chunk_id": chunk_id, "title": f"Case {chunk_id}"},
        ),
        0.8,
    )


async def test_the_prompt_carries_the_question_and_both_blocks(monkeypatch) -> None:
    prompts = _install_model_stub(monkeypatch, "Refunded [1].")

    await lookup_module.lookup_generate(
        {"query": "cases where a refund was issued", "policy_hits": [_policy_hit()], "case_hits": [_case_hit("c1")]}
    )

    prompt = prompts[0]
    assert "<question>\ncases where a refund was issued\n</question>" in prompt
    assert "[1] Billing Policy" in prompt
    # Cases number on from the last policy extract.
    assert "[2] Case c1" in prompt


async def test_a_cases_only_lookup_returns_only_the_cited_cases(monkeypatch) -> None:
    _install_model_stub(monkeypatch, "- Charged twice, duplicate refunded [2].")

    update = await lookup_module.lookup_generate(
        {"query": "refund cases", "policy_hits": [], "case_hits": [_case_hit("c1"), _case_hit("c2")]}
    )

    assert update["draft"] == "- Charged twice, duplicate refunded [2]."
    assert [(citation.marker, citation.doc_type) for citation in update["citations"]] == [(2, "case")]
