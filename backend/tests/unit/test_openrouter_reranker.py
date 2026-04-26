import pytest
from langchain_core.documents import Document

from cms.retrieval.rerank import openrouter_reranker


class _StubReranker:
    """Stands in for OpenRouterRerank: reverses the order and scores by position."""

    def __init__(self) -> None:
        self.calls: list[dict] = []

    async def acompress_documents(self, documents, query):
        self.calls.append({"documents": list(documents), "query": query})
        return [
            Document(
                document.page_content,
                metadata={**document.metadata, "relevance_score": 0.9 - index / 10},
            )
            for index, document in enumerate(reversed(documents))
        ]


def _install_stub(monkeypatch) -> _StubReranker:
    reranker = _StubReranker()
    monkeypatch.setattr(openrouter_reranker, "get_reranker", lambda top_n: reranker)
    return reranker


def _canned_hits() -> list[tuple[Document, float]]:
    return [
        (Document(page_content="Warranty > 2.3 Defects", metadata={"doc_id": "p1"}), 0.82),
        (Document(page_content="Returns > 1.1 Window", metadata={"doc_id": "p2"}), 0.41),
    ]


async def test_empty_hits_short_circuits(monkeypatch) -> None:
    # An empty pool must not cost an API round trip.
    reranker = _install_stub(monkeypatch)

    assert await openrouter_reranker.rerank_documents("warranty", [], top_n=5) == []
    assert reranker.calls == []


async def test_sends_the_documents_and_returns_relevance_scores(monkeypatch) -> None:
    reranker = _install_stub(monkeypatch)
    hits = _canned_hits()

    result = await openrouter_reranker.rerank_documents("warranty", hits, top_n=5)

    assert reranker.calls[0]["query"] == "warranty"
    assert reranker.calls[0]["documents"] == [document for document, _ in hits]
    # Reranked order, and the float slot now carries the rerank score, not Qdrant's.
    assert [document.page_content for document, _ in result] == [
        "Returns > 1.1 Window",
        "Warranty > 2.3 Defects",
    ]
    assert [score for _, score in result] == [0.9, 0.8]


async def test_rejects_an_oversized_pool(monkeypatch) -> None:
    _install_stub(monkeypatch)
    hits = _canned_hits() * (openrouter_reranker.MAX_DOCUMENTS // 2 + 1)

    with pytest.raises(ValueError, match="at most"):
        await openrouter_reranker.rerank_documents("warranty", hits, top_n=5)
