import pytest
from langchain_core.documents import Document
from langchain_qdrant import RetrievalMode

from cms.retrieval import case_retriever

# Every assertion below holds for all three legs — only the mode the store is
# opened in differs.
ALL_MODES = pytest.mark.parametrize(
    ("retrieve", "expected_mode"),
    [
        (case_retriever.retrieve_cases_dense, RetrievalMode.DENSE),
        (case_retriever.retrieve_cases_sparse, RetrievalMode.SPARSE),
        (case_retriever.retrieve_cases_hybrid, RetrievalMode.HYBRID),
    ],
)


class _StubStore:
    """Records what the retriever asked for and returns canned hits."""

    def __init__(self, hits: list[tuple[Document, float]]) -> None:
        self.hits = hits
        self.calls: list[dict] = []

    def similarity_search_with_score(self, query, k, filter=None):
        self.calls.append({"query": query, "k": k, "filter": filter})
        return self.hits


def _install_stub(monkeypatch, hits: list[tuple[Document, float]]) -> _StubStore:
    """Point the retriever at a stub store and a fixed collection name."""
    store = _StubStore(hits)
    opened: list[dict] = []

    def fake_get_vector_store(collection_name, mode):
        opened.append({"collection_name": collection_name, "mode": mode})
        return store

    monkeypatch.setattr(case_retriever, "get_vector_store", fake_get_vector_store)
    monkeypatch.setattr(
        case_retriever,
        "get_settings",
        lambda: type("S", (), {"qdrant_cases_collection": "cases_test"})(),
    )
    store.opened = opened
    return store


def _canned_hits() -> list[tuple[Document, float]]:
    return [
        (Document(page_content="COMPLAINT: won't charge", metadata={"doc_id": "c1"}), 0.82),
        (Document(page_content="COMPLAINT: arrived damaged", metadata={"doc_id": "c2"}), 0.41),
    ]


@ALL_MODES
def test_opens_the_cases_collection_in_its_own_mode(
    monkeypatch, retrieve, expected_mode
) -> None:
    store = _install_stub(monkeypatch, _canned_hits())

    retrieve("vacuum stopped charging")

    assert store.opened == [{"collection_name": "cases_test", "mode": expected_mode}]


@ALL_MODES
def test_passes_query_and_k_through(monkeypatch, retrieve, expected_mode) -> None:
    store = _install_stub(monkeypatch, _canned_hits())

    retrieve("vacuum stopped charging", k=8)

    assert store.calls[0]["query"] == "vacuum stopped charging"
    assert store.calls[0]["k"] == 8


@ALL_MODES
def test_defaults_k(monkeypatch, retrieve, expected_mode) -> None:
    store = _install_stub(monkeypatch, _canned_hits())

    retrieve("vacuum stopped charging")

    assert store.calls[0]["k"] == case_retriever.DEFAULT_K


@ALL_MODES
def test_searches_unfiltered(monkeypatch, retrieve, expected_mode) -> None:
    # Unlike policies, cases have no `lifecycle` to gate on — every point in the
    # collection is already a resolved case.
    store = _install_stub(monkeypatch, _canned_hits())

    retrieve("vacuum stopped charging")

    assert store.calls[0]["filter"] is None


@ALL_MODES
def test_returns_hits_unchanged_and_in_order(monkeypatch, retrieve, expected_mode) -> None:
    hits = _canned_hits()
    _install_stub(monkeypatch, hits)

    assert retrieve("vacuum stopped charging") == hits
