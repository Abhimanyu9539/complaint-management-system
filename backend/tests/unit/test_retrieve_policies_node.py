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


def _install_rerank_stub(monkeypatch) -> list[dict]:
    """Replace the reranker with a recorder that just truncates — the live one bills."""
    calls: list[dict] = []

    async def fake_rerank(
        query: str, hits: list[tuple[Document, float]], top_n: int
    ) -> list[tuple[Document, float]]:
        calls.append({"query": query, "hits": hits, "top_n": top_n})
        return hits[:top_n]

    monkeypatch.setattr(retrieve_module, "rerank_documents", fake_rerank)
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

    # rerank=False so this stays a test of the merge, not of what ranks the merge.
    hits = await retrieve_module.retrieve_policies_core(["a", "b"], rerank=False)

    assert [(doc.metadata["chunk_id"], score) for doc, score in hits] == [
        ("c2", 0.9),
        ("c1", 0.7),
    ]


async def test_merged_union_is_reranked_once_against_the_original_query(monkeypatch) -> None:
    _install_stub(
        monkeypatch,
        {
            "complaint": [(_chunk("c1"), 0.9), (_chunk("c2"), 0.5)],
            "rewrite": [(_chunk("c3"), 0.8)],
        },
    )
    rerank_calls = _install_rerank_stub(monkeypatch)

    update = await retrieve_module.retrieve_policies(
        {"query": "complaint", "policy_queries": ["complaint", "rewrite"]}
    )

    # One call over the union, not one per query, and ranked by the customer's
    # own wording rather than by a rewrite.
    assert len(rerank_calls) == 1
    assert rerank_calls[0]["query"] == "complaint"
    assert len(rerank_calls[0]["hits"]) == 3
    # Union smaller than top_n, so nothing is dropped — capping is covered below.
    assert len(update["policy_hits"]) == 3
    assert update["no_match"] is False


async def test_rerank_caps_the_context_at_top_n(monkeypatch) -> None:
    _install_stub(monkeypatch, {"q": [(_chunk(f"c{i}"), 1 - i / 100) for i in range(30)]})
    _install_rerank_stub(monkeypatch)

    hits = await retrieve_module.retrieve_policies_core(["q"], rerank=True, top_n=10)

    assert len(hits) == 10


async def test_no_policy_queries_skips_retrieval(monkeypatch) -> None:
    calls = _install_stub(monkeypatch, {})

    update = await retrieve_module.retrieve_policies({"query": "hi", "policy_queries": []})

    assert calls == []
    assert update == {"policy_hits": [], "no_match": True}
