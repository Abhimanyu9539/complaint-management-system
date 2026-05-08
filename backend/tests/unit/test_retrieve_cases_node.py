import pytest
from langchain_core.documents import Document

from cms.rag.nodes import retrieve_cases as retrieve_module


def _chunk(chunk_id: str) -> Document:
    return Document(page_content=f"text of {chunk_id}", metadata={"chunk_id": chunk_id})


def _install_stub(monkeypatch, hits: list[tuple[Document, float]]) -> list[dict]:
    """Replace the retriever with a recorder returning canned hits."""
    calls: list[dict] = []

    async def fake_retrieve(query: str, **kwargs) -> list[tuple[Document, float]]:
        calls.append({"query": query, **kwargs})
        return hits

    monkeypatch.setattr(retrieve_module, "retrieve_cases_hybrid", fake_retrieve)
    return calls


async def test_searches_the_original_query_only(monkeypatch) -> None:
    hits = [(_chunk("c1"), 0.9), (_chunk("c2"), 0.5)]
    calls = _install_stub(monkeypatch, hits)

    update = await retrieve_module.retrieve_cases(
        {"query": "my vacuum stopped charging", "policy_queries": ["warranty coverage"]}
    )

    # One search with the customer's wording — the policy rewrites are not used.
    assert [call["query"] for call in calls] == ["my vacuum stopped charging"]
    assert update == {"case_hits": hits}


async def test_no_cases_does_not_set_no_match(monkeypatch) -> None:
    _install_stub(monkeypatch, [])

    update = await retrieve_module.retrieve_cases({"query": "q"})

    # `no_match` belongs to the policy branch; zero similar cases must not block a draft.
    assert update == {"case_hits": []}


async def test_retriever_error_propagates(monkeypatch) -> None:
    async def failing_retrieve(query: str, **kwargs) -> list[tuple[Document, float]]:
        raise RuntimeError("qdrant down")

    monkeypatch.setattr(retrieve_module, "retrieve_cases_hybrid", failing_retrieve)

    with pytest.raises(RuntimeError):
        await retrieve_module.retrieve_cases({"query": "q"})
