import pytest
from langchain_core.documents import Document

from cms.config.settings import get_settings
from cms.rag.nodes import retrieve_cases as retrieve_module


def _chunk(chunk_id: str) -> Document:
    return Document(page_content=f"text of {chunk_id}", metadata={"chunk_id": chunk_id})


def _install_stub(
    monkeypatch, hits: list[tuple[Document, float]], rerank: bool = True
) -> list[dict]:
    """Replace the pool-and-rerank helper with a recorder returning canned hits."""
    calls: list[dict] = []

    async def fake_retrieve(query: str, pool_k: int, top_n: int) -> list[tuple[Document, float]]:
        calls.append({"query": query, "pool_k": pool_k, "top_n": top_n})
        return hits

    monkeypatch.setattr(retrieve_module, "retrieve_cases_reranked", fake_retrieve)
    monkeypatch.setattr(get_settings(), "rerank_enabled", rerank)
    monkeypatch.setattr(get_settings(), "case_relevance_threshold", 0.5)
    return calls


async def test_searches_the_original_query_only(monkeypatch) -> None:
    hits = [(_chunk("c1"), 0.9), (_chunk("c2"), 0.6)]
    calls = _install_stub(monkeypatch, hits)

    update = await retrieve_module.retrieve_cases(
        {"query": "my vacuum stopped charging", "policy_queries": ["warranty coverage"]}
    )

    # One search with the customer's wording — the policy rewrites are not used.
    assert calls == [
        {
            "query": "my vacuum stopped charging",
            "pool_k": get_settings().case_pool_k,
            "top_n": get_settings().case_top_k,
        }
    ]
    assert update == {"case_hits": hits}


async def test_cases_below_the_floor_are_dropped(monkeypatch) -> None:
    strong, at_floor, weak = (_chunk("c1"), 0.9), (_chunk("c2"), 0.5), (_chunk("c3"), 0.44)
    _install_stub(monkeypatch, [strong, at_floor, weak])

    update = await retrieve_module.retrieve_cases({"query": "q"})

    # Per case, not a best-score gate: the weak case does not ride along with the strong one.
    assert update == {"case_hits": [strong, at_floor]}


async def test_without_reranking_the_hits_pass_unfiltered(monkeypatch) -> None:
    # RRF scores are on another scale, so the floor does not apply.
    hits = [(_chunk("c1"), 0.03), (_chunk("c2"), 0.02)]
    _install_stub(monkeypatch, hits, rerank=False)

    update = await retrieve_module.retrieve_cases({"query": "q"})

    assert update == {"case_hits": hits}


async def test_no_cases_does_not_set_no_match(monkeypatch) -> None:
    _install_stub(monkeypatch, [])

    update = await retrieve_module.retrieve_cases({"query": "q"})

    # `no_match` belongs to the policy branch; zero similar cases must not block a draft.
    assert update == {"case_hits": []}


async def test_retriever_error_propagates(monkeypatch) -> None:
    async def failing_retrieve(query: str, pool_k: int, top_n: int) -> list[tuple[Document, float]]:
        raise RuntimeError("qdrant down")

    monkeypatch.setattr(retrieve_module, "retrieve_cases_reranked", failing_retrieve)

    with pytest.raises(RuntimeError):
        await retrieve_module.retrieve_cases({"query": "q"})
