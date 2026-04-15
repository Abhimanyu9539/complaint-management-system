from langchain_core.documents import Document
from langchain_qdrant import RetrievalMode

from cms.retrieval import policy_retriever


class _StubStore:
    """Records what the retriever asked for and returns canned hits."""

    def __init__(self, hits: list[tuple[Document, float]]) -> None:
        self.hits = hits
        self.calls: list[dict] = []

    def similarity_search_with_score(self, query, k, filter):
        self.calls.append({"query": query, "k": k, "filter": filter})
        return self.hits


def _install_stub(monkeypatch, hits: list[tuple[Document, float]]) -> _StubStore:
    """Point the retriever at a stub store and a fixed collection name."""
    store = _StubStore(hits)
    opened: list[dict] = []

    def fake_get_vector_store(collection_name, mode):
        opened.append({"collection_name": collection_name, "mode": mode})
        return store

    monkeypatch.setattr(policy_retriever, "get_vector_store", fake_get_vector_store)
    monkeypatch.setattr(
        policy_retriever,
        "get_settings",
        lambda: type("S", (), {"qdrant_policies_collection": "policies_test"})(),
    )
    store.opened = opened
    return store


def _canned_hits() -> list[tuple[Document, float]]:
    return [
        (Document(page_content="Warranty > 2.3 Defects", metadata={"doc_id": "p1"}), 0.82),
        (Document(page_content="Returns > 1.1 Window", metadata={"doc_id": "p2"}), 0.41),
    ]


def test_retrieve_policies_opens_the_policies_collection_in_dense_mode(monkeypatch) -> None:
    store = _install_stub(monkeypatch, _canned_hits())

    policy_retriever.retrieve_policies("warranty period")

    assert store.opened == [
        {"collection_name": "policies_test", "mode": RetrievalMode.DENSE}
    ]


def test_retrieve_policies_passes_query_and_k_through(monkeypatch) -> None:
    store = _install_stub(monkeypatch, _canned_hits())

    policy_retriever.retrieve_policies("warranty period", k=8)

    assert store.calls[0]["query"] == "warranty period"
    assert store.calls[0]["k"] == 8


def test_retrieve_policies_defaults_k(monkeypatch) -> None:
    store = _install_stub(monkeypatch, _canned_hits())

    policy_retriever.retrieve_policies("warranty period")

    assert store.calls[0]["k"] == policy_retriever.DEFAULT_K


def test_retrieve_policies_filters_published_on_the_dotted_metadata_path(monkeypatch) -> None:
    # The one mistake here that fails silently: a filter on the bare name
    # `lifecycle` matches zero points instead of raising.
    store = _install_stub(monkeypatch, _canned_hits())

    policy_retriever.retrieve_policies("warranty period")

    conditions = store.calls[0]["filter"].must
    assert len(conditions) == 1
    assert conditions[0].key == "metadata.lifecycle"
    assert conditions[0].match.value == "published"


def test_retrieve_policies_returns_hits_unchanged_and_in_order(monkeypatch) -> None:
    hits = _canned_hits()
    _install_stub(monkeypatch, hits)

    assert policy_retriever.retrieve_policies("warranty period") == hits
