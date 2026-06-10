from langchain_core.documents import Document

from cms.config.settings import get_settings
from cms.rag.nodes import lookup_retrieve_cases as cases_module

HIT = (Document(page_content="past case", metadata={"chunk_id": "c1"}), 0.03)
STATE = {"query": "cases where a refund was issued", "lookup_target": "cases"}


def _install(monkeypatch, score: float = 0.9) -> dict[str, list]:
    """Stub the Qdrant search and the reranker; the reranker gives every hit `score`."""
    calls: dict[str, list] = {"search": [], "rerank": []}

    async def fake_search(query, k):
        calls["search"].append({"query": query, "k": k})
        return [HIT]

    async def fake_rerank(query, hits, top_n):
        calls["rerank"].append({"query": query, "top_n": top_n})
        return [(document, score) for document, _ in hits][:top_n]

    monkeypatch.setattr(cases_module, "retrieve_cases_hybrid", fake_search)
    monkeypatch.setattr(cases_module, "rerank_documents", fake_rerank)
    monkeypatch.setattr(get_settings(), "rerank_enabled", True)
    monkeypatch.setattr(get_settings(), "lookup_case_relevance_threshold", 0.5)
    return calls


async def test_a_policies_only_lookup_skips_the_search(monkeypatch) -> None:
    calls = _install(monkeypatch)

    update = await cases_module.lookup_retrieve_cases({**STATE, "lookup_target": "policies"})

    assert update == {"case_hits": []}
    assert calls["search"] == []


async def test_the_wording_is_searched_in_a_wide_pool_then_reranked(monkeypatch) -> None:
    calls = _install(monkeypatch)

    update = await cases_module.lookup_retrieve_cases(STATE)

    assert calls["search"] == [
        {"query": "cases where a refund was issued", "k": get_settings().lookup_case_pool_k}
    ]
    assert calls["rerank"] == [
        {"query": "cases where a refund was issued", "top_n": get_settings().lookup_case_top_n}
    ]
    assert update == {"case_hits": [(HIT[0], 0.9)]}


async def test_cases_below_the_gate_are_dropped(monkeypatch) -> None:
    _install(monkeypatch, score=0.2)

    update = await cases_module.lookup_retrieve_cases(STATE)

    assert update == {"case_hits": []}


async def test_without_reranking_the_hybrid_hits_pass_ungated(monkeypatch) -> None:
    calls = _install(monkeypatch)
    monkeypatch.setattr(get_settings(), "rerank_enabled", False)

    hits = await cases_module.retrieve_lookup_cases_core("refunds")

    assert hits == [HIT]
    assert calls["rerank"] == []
