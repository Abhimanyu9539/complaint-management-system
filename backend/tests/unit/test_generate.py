from langchain_core.documents import Document
from langchain_core.runnables import RunnableLambda

from cms.rag.nodes import generate as generate_module
from cms.schemas.generation import Citation


class _FakeMessage:
    def __init__(self, content: str) -> None:
        self.content = content


def _install_model_stub(monkeypatch, reply: str) -> list[str]:
    """Replace only the chat model, so nothing reaches OpenRouter.

    A `RunnableLambda` rather than a bare object: the real `generate/v1`
    template still renders and pipes into it, so these tests also prove the
    prompt interpolates — which a hand-rolled chain stub would skip.
    """
    prompts: list[str] = []

    def fake_model(prompt_value) -> _FakeMessage:
        prompts.append(prompt_value.to_string())
        return _FakeMessage(reply)

    monkeypatch.setattr(
        generate_module, "get_chat_model", lambda model: RunnableLambda(fake_model)
    )
    return prompts


def _hit(chunk_id: str, title: str = "Warranty Policy") -> tuple[Document, float]:
    return (
        Document(
            page_content=f"{title} > 2.3 Defects\n\ncovered for replacement",
            metadata={"doc_id": "doc-1", "chunk_id": chunk_id, "title": title},
        ),
        0.9,
    )


async def test_the_model_is_given_the_built_context_and_the_query(monkeypatch) -> None:
    prompts = _install_model_stub(monkeypatch, "Covered under warranty [1].")

    await generate_module.generate_core("my unit stopped charging", [_hit("c1")])

    # Both variables interpolated into the real generate/v1 template.
    assert "my unit stopped charging" in prompts[0]
    assert "[1] Warranty Policy" in prompts[0]  # the numbered block, not raw chunks
    assert "{context}" not in prompts[0]


async def test_only_the_cited_chunks_come_back(monkeypatch) -> None:
    _install_model_stub(monkeypatch, "Covered [1], and the remedy is replacement [3].")

    _, citations = await generate_module.generate_core(
        "q", [_hit("c1"), _hit("c2"), _hit("c3")]
    )

    # [2] was offered and not cited, so it is not presented as a source.
    assert [citation.marker for citation in citations] == [1, 3]
    assert [citation.chunk_id for citation in citations] == ["c1", "c3"]


async def test_node_returns_the_draft_and_citations(monkeypatch) -> None:
    seen: list[tuple] = []
    citation = Citation(marker=1, doc_id="d", chunk_id="c", title="t", section="s")

    async def fake_core(query, hits):
        seen.append((query, hits))
        return "the draft [1]", [citation]

    monkeypatch.setattr(generate_module, "generate_core", fake_core)
    hits = [_hit("c1")]

    update = await generate_module.generate({"query": "complaint", "policy_hits": hits})

    assert update == {"draft": "the draft [1]", "citations": [citation]}
    assert seen == [("complaint", hits)]


async def test_no_hits_does_not_crash(monkeypatch) -> None:
    """The graph routes empty retrieval to no_match, but the function stands alone."""
    prompts = _install_model_stub(monkeypatch, "Nothing in policy covers this.")

    draft, citations = await generate_module.generate_core("q", [])

    # No chunk text reached the model. Not asserted via "[1]" — the system
    # prompt uses bracket numbers to explain the citation format.
    assert "Warranty Policy" not in prompts[0]
    assert citations == []
    assert draft
