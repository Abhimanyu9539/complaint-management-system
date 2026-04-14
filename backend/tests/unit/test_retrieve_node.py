from cms.rag.nodes import retrieve as retrieve_module
from cms.rag.nodes.retrieve import select_departments
from cms.retrieval.retrievers.hybrid_retriever import RetrievalResult

THRESHOLD = 0.60


# ---------------------------------------------------------------------------
# select_departments
# ---------------------------------------------------------------------------


def test_confident_top_candidate_uses_only_that_department() -> None:
    candidates = [{"department": "warranty", "confidence": 0.9}]

    assert select_departments(candidates, THRESHOLD) == ["warranty"]


def test_low_confidence_with_second_candidate_widens_to_both() -> None:
    candidates = [
        {"department": "billing", "confidence": 0.4},
        {"department": "retention", "confidence": 0.3},
    ]

    assert select_departments(candidates, THRESHOLD) == ["billing", "retention"]


def test_low_confidence_with_only_one_candidate_has_nothing_to_widen_to() -> None:
    candidates = [{"department": "billing", "confidence": 0.4}]

    assert select_departments(candidates, THRESHOLD) == ["billing"]


def test_low_confidence_widening_caps_at_top_two_of_three() -> None:
    candidates = [
        {"department": "billing", "confidence": 0.4},
        {"department": "retention", "confidence": 0.3},
        {"department": "sales", "confidence": 0.1},
    ]

    assert select_departments(candidates, THRESHOLD) == ["billing", "retention"]


def test_no_candidates_means_unfiltered() -> None:
    assert select_departments([], THRESHOLD) is None


# ---------------------------------------------------------------------------
# retrieve_node
# ---------------------------------------------------------------------------


def _empty_result(**kwargs) -> RetrievalResult:
    return RetrievalResult(cases=[], policies=[], queries=["q"], departments=kwargs.get("departments"))


def test_retrieve_node_uses_widened_departments_and_rewritten_queries(monkeypatch) -> None:
    calls: list[dict] = []

    def fake_retrieve(query, *, departments=None, **kwargs):
        calls.append({"query": query, "departments": departments})
        return _empty_result(departments=departments)

    monkeypatch.setattr(retrieve_module, "hybrid_retrieve", fake_retrieve)

    state = {
        "query": "raw complaint text",
        "search_queries": ["rewritten query one", "rewritten query two"],
        "department_candidates": [
            {"department": "billing", "confidence": 0.4},
            {"department": "retention", "confidence": 0.3},
        ],
    }

    update = retrieve_module.retrieve_node(state)

    assert calls[0]["query"] == ["rewritten query one", "rewritten query two"]
    assert calls[0]["departments"] == ["billing", "retention"]
    assert update["retrieved"] == []
    assert update["retrieval_attempts"] == 1


def test_retrieve_node_falls_back_to_raw_query_when_no_search_queries(monkeypatch) -> None:
    calls: list[dict] = []

    def fake_retrieve(query, *, departments=None, **kwargs):
        calls.append({"query": query})
        return _empty_result()

    monkeypatch.setattr(retrieve_module, "hybrid_retrieve", fake_retrieve)

    retrieve_module.retrieve_node({"query": "just the raw query"})

    assert calls[0]["query"] == ["just the raw query"]


def test_retrieve_node_increments_existing_attempt_count(monkeypatch) -> None:
    monkeypatch.setattr(
        retrieve_module, "hybrid_retrieve", lambda query, **kwargs: _empty_result()
    )

    update = retrieve_module.retrieve_node({"query": "q", "retrieval_attempts": 1})

    assert update["retrieval_attempts"] == 2
