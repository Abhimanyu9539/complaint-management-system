from langchain_core.documents import Document
from langchain_core.runnables import RunnableLambda

from cms.rag.nodes import generate as generate_module
from cms.schemas.generation import Citation


class _FakeMessage:
    def __init__(self, content: str) -> None:
        self.content = content


def _install_model_stub(monkeypatch, reply: str) -> list[str]:
    """Replace only the chat model, so nothing reaches OpenRouter.

    A `RunnableLambda` rather than a bare object: the real `generate/v3`
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


def _case_hit(chunk_id: str) -> tuple[Document, float]:
    """A case chunk shaped the way `build_case_text` writes them."""
    return (
        Document(
            page_content="COMPLAINT:\nvacuum stopped charging\n\nRESOLUTION:\nreplacement issued",
            metadata={
                "doc_id": "case-1",
                "chunk_id": chunk_id,
                "title": "C-1001 — warranty / faulty_product",
            },
        ),
        0.8,
    )


async def test_the_model_is_given_the_built_context_and_the_query(monkeypatch) -> None:
    prompts = _install_model_stub(monkeypatch, "Covered under warranty [1].")

    await generate_module.generate_core("my unit stopped charging", [_hit("c1")], [])

    # Every variable interpolated into the real generate/v3 template.
    assert "my unit stopped charging" in prompts[0]
    assert "[1] Warranty Policy" in prompts[0]  # the numbered block, not raw chunks
    assert "{context}" not in prompts[0]
    assert "{cases}" not in prompts[0]


async def test_cases_are_numbered_after_policies_and_cited_as_cases(monkeypatch) -> None:
    prompts = _install_model_stub(monkeypatch, "Covered [1]; a similar case was replaced [2].")

    _, citations = await generate_module.generate_core("q", [_hit("p1")], [_case_hit("k1")])

    # The case sits in its own section, numbered on from the policy extracts.
    assert prompts[0].index("<past_cases>") < prompts[0].index("[2] C-1001")
    assert [citation.doc_type for citation in citations] == ["policy", "case"]
    assert [citation.doc_id for citation in citations] == ["doc-1", "case-1"]


async def test_only_the_cited_chunks_come_back(monkeypatch) -> None:
    _install_model_stub(monkeypatch, "Covered [1], and the remedy is replacement [3].")

    _, citations = await generate_module.generate_core(
        "q", [_hit("c1"), _hit("c2"), _hit("c3")], []
    )

    # [2] was offered and not cited, so it is not presented as a source.
    assert [citation.marker for citation in citations] == [1, 3]
    assert [citation.chunk_id for citation in citations] == ["c1", "c3"]


async def test_node_returns_the_draft_and_citations(monkeypatch) -> None:
    seen: list[tuple] = []
    citation = Citation(marker=1, doc_id="d", chunk_id="c", title="t", section="s")

    async def fake_core(query, policy_hits, case_hits, feedback=None):
        seen.append((query, policy_hits, case_hits, feedback))
        return "the draft [1]", [citation]

    monkeypatch.setattr(generate_module, "generate_core", fake_core)
    hits = [_hit("c1")]
    case_hits = [_case_hit("k1")]

    update = await generate_module.generate(
        {"query": "complaint", "policy_hits": hits, "case_hits": case_hits}
    )

    assert update == {"draft": "the draft [1]", "citations": [citation]}
    assert seen == [("complaint", hits, case_hits, None)]


async def test_no_hits_does_not_crash(monkeypatch) -> None:
    """The graph routes empty retrieval to no_match, but the function stands alone."""
    prompts = _install_model_stub(monkeypatch, "Nothing in policy covers this.")

    draft, citations = await generate_module.generate_core("q", [], [])

    # No chunk text reached the model. Not asserted via "[1]" — the system
    # prompt uses bracket numbers to explain the citation format.
    assert "Warranty Policy" not in prompts[0]
    assert citations == []
    assert draft


async def test_first_draft_has_no_feedback_block(monkeypatch) -> None:
    prompts = _install_model_stub(monkeypatch, "Covered [1].")

    await generate_module.generate_core("q", [_hit("c1")], [])

    # The system prompt names the section; only a retry renders one.
    assert "<feedback>\n-" not in prompts[0]
    assert "{feedback}" not in prompts[0]


async def test_guard_reasons_reach_the_prompt_as_feedback(monkeypatch) -> None:
    prompts = _install_model_stub(monkeypatch, "Covered [1].")

    await generate_module.generate_core("q", [_hit("c1")], [], feedback=["Cite every claim."])

    assert "<feedback>\n- Cite every claim.\n</feedback>" in prompts[0]


async def test_node_retries_with_feedback_after_an_ungrounded_draft(monkeypatch) -> None:
    seen: list[list[str] | None] = []

    async def fake_core(query, policy_hits, case_hits, feedback=None):
        seen.append(feedback)
        return "better draft [1]", []

    monkeypatch.setattr(generate_module, "generate_core", fake_core)

    update = await generate_module.generate(
        {"query": "q", "grounded": False, "guard_reasons": ["uncited claim"]}
    )

    assert seen == [["uncited claim"]]
    assert update["regenerated"] is True
