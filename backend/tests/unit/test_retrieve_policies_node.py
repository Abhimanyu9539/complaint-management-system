from langchain_core.documents import Document

from cms.rag.nodes import retrieve_policies as retrieve_module


def _chunk(chunk_id: str) -> Document:
    return Document(page_content=f"text of {chunk_id}", metadata={"chunk_id": chunk_id})


def _install_stub(monkeypatch, by_query: dict[str, list[tuple[Document, float]]]) -> list[dict]:
    """Replace the retriever with a recorder returning canned hits per query."""
    calls: list[dict] = []

    async def fake_retrieve(query: str, **kwargs) -> list[tuple[Document, float]]:
        calls.append({"query": query, **kwargs})
        return by_query.get(query, [])

    monkeypatch.setattr(retrieve_module, "retrieve_policies_hybrid", fake_retrieve)
    return calls


async def test_every_query_is_searched_without_reranking(monkeypatch) -> None:
    calls = _install_stub(monkeypatch, {})

    await retrieve_module.retrieve_policies(
        {"query": "q", "policy_queries": ["warranty coverage", "refund window"]}
    )

    assert [call["query"] for call in calls] == ["warranty coverage", "refund window"]
    # The retriever's default is on, which would reach the live OpenRouter API.
    assert all(call["rerank"] is False for call in calls)


async def test_duplicate_chunks_collapse_to_the_best_score(monkeypatch) -> None:
    shared = _chunk("c1")
    _install_stub(
        monkeypatch,
        {
            "a": [(shared, 0.3), (_chunk("c2"), 0.9)],
            "b": [(shared, 0.7)],
        },
    )

    update = await retrieve_module.retrieve_policies({"query": "q", "policy_queries": ["a", "b"]})

    assert [(doc.metadata["chunk_id"], score) for doc, score in update["policy_hits"]] == [
        ("c2", 0.9),
        ("c1", 0.7),
    ]
    assert update["no_match"] is False


async def test_no_policy_queries_skips_retrieval(monkeypatch) -> None:
    calls = _install_stub(monkeypatch, {})

    update = await retrieve_module.retrieve_policies({"query": "hi", "policy_queries": []})

    assert calls == []
    assert update == {"policy_hits": [], "no_match": True}
