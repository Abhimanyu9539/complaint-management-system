from langchain_core.documents import Document

from cms.config.settings import get_settings
from cms.rag.nodes import lookup_retrieve_policies as policies_module

HIT = (Document(page_content="policy clause", metadata={"chunk_id": "p1"}), 0.03)
STATE = {
    "query": "what is the return window?",
    "lookup_target": "policies",
    "policy_queries": ["what is the return window?", "return window eligibility"],
}


def _install(monkeypatch, score: float = 0.9) -> dict[str, list]:
    """Stub the Qdrant search and the reranker; the reranker gives every hit `score`."""
    calls: dict[str, list] = {"search": [], "rerank": []}

    async def fake_search(query, rerank):
        calls["search"].append({"query": query, "rerank": rerank})
        return [HIT]

    async def fake_rerank(query, hits, top_n):
        calls["rerank"].append({"query": query, "top_n": top_n})
        return [(document, score) for document, _ in hits][:top_n]

    monkeypatch.setattr(policies_module, "retrieve_policies_hybrid", fake_search)
    monkeypatch.setattr(policies_module, "rerank_documents", fake_rerank)
    monkeypatch.setattr(get_settings(), "rerank_enabled", True)
    monkeypatch.setattr(get_settings(), "policy_relevance_threshold", 0.5)
    return calls


async def test_a_cases_only_lookup_skips_the_search(monkeypatch) -> None:
    calls = _install(monkeypatch)

    update = await policies_module.lookup_retrieve_policies({**STATE, "lookup_target": "cases"})

    assert update == {"policy_hits": []}
    assert calls["search"] == []


async def test_every_query_is_searched_then_reranked_once_against_the_wording(monkeypatch) -> None:
    calls = _install(monkeypatch)

    update = await policies_module.lookup_retrieve_policies(STATE)

    assert calls["search"] == [
        {"query": "what is the return window?", "rerank": False},
        {"query": "return window eligibility", "rerank": False},
    ]
    assert calls["rerank"] == [
        {"query": "what is the return window?", "top_n": get_settings().policy_rerank_top_n}
    ]
    assert update == {"policy_hits": [(HIT[0], 0.9)]}


async def test_policies_below_the_gate_are_dropped(monkeypatch) -> None:
    _install(monkeypatch, score=0.2)

    update = await policies_module.lookup_retrieve_policies(STATE)

    assert update == {"policy_hits": []}


async def test_without_reranking_the_hybrid_hits_pass_ungated(monkeypatch) -> None:
    calls = _install(monkeypatch)
    monkeypatch.setattr(get_settings(), "rerank_enabled", False)

    hits = await policies_module.retrieve_lookup_policies_core(["refunds"])

    # An RRF score of 0.03 would fail a 0.5 gate — it must not be gated at all.
    assert hits == [HIT]
    assert calls["rerank"] == []


def test_merge_keeps_the_best_score_for_a_chunk_found_twice() -> None:
    document = Document(page_content="clause", metadata={"chunk_id": "p1"})
    other = Document(page_content="other", metadata={"chunk_id": "p2"})

    merged = policies_module._merge_hits([[(document, 0.2), (other, 0.5)], [(document, 0.7)]])

    assert merged == [(document, 0.7), (other, 0.5)]
