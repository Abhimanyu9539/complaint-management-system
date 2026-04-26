import pytest
from langchain_core.documents import Document
from langchain_qdrant import RetrievalMode

from cms.retrieval.retrievers import policy_retriever

# Every assertion below holds for all three legs — only the mode the store is
# opened in differs. They all pass `rerank=False`: these cover the Qdrant call,
# and the default is on, which would reach the live Voyage API. The rerank path
# gets its own stubbed group at the bottom.
ALL_MODES = pytest.mark.parametrize(
    ("retrieve", "expected_mode"),
    [
        (policy_retriever.retrieve_policies_dense, RetrievalMode.DENSE),
        (policy_retriever.retrieve_policies_sparse, RetrievalMode.SPARSE),
        (policy_retriever.retrieve_policies_hybrid, RetrievalMode.HYBRID),
    ],
)


class _StubStore:
    """Records what the retriever asked for and returns canned hits."""

    def __init__(self, hits: list[tuple[Document, float]]) -> None:
        self.hits = hits
        self.calls: list[dict] = []

    async def asimilarity_search_with_score(self, query, k, filter):
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


@ALL_MODES
async def test_opens_the_policies_collection_in_its_own_mode(
    monkeypatch, retrieve, expected_mode
) -> None:
    store = _install_stub(monkeypatch, _canned_hits())

    await retrieve("warranty period", rerank=False)

    assert store.opened == [
        {"collection_name": "policies_test", "mode": expected_mode}
    ]


@ALL_MODES
async def test_passes_query_and_k_through(monkeypatch, retrieve, expected_mode) -> None:
    store = _install_stub(monkeypatch, _canned_hits())

    await retrieve("warranty period", k=8, rerank=False)

    assert store.calls[0]["query"] == "warranty period"
    assert store.calls[0]["k"] == 8


@ALL_MODES
async def test_defaults_k(monkeypatch, retrieve, expected_mode) -> None:
    store = _install_stub(monkeypatch, _canned_hits())

    await retrieve("warranty period", rerank=False)

    assert store.calls[0]["k"] == policy_retriever.DEFAULT_K


@ALL_MODES
async def test_filters_published_on_the_dotted_metadata_path(
    monkeypatch, retrieve, expected_mode
) -> None:
    # The one mistake here that fails silently: a filter on the bare name
    # `lifecycle` matches zero points instead of raising.
    store = _install_stub(monkeypatch, _canned_hits())

    await retrieve("warranty period", rerank=False)

    conditions = store.calls[0]["filter"].must
    assert len(conditions) == 1
    assert conditions[0].key == "metadata.lifecycle"
    assert conditions[0].match.value == "published"


@ALL_MODES
async def test_returns_hits_unchanged_and_in_order(monkeypatch, retrieve, expected_mode) -> None:
    hits = _canned_hits()
    _install_stub(monkeypatch, hits)

    assert await retrieve("warranty period", rerank=False) == hits


# --- Reranking ---------------------------------------------------------------


def _install_rerank_stub(monkeypatch) -> list[dict]:
    """Replace the reranker with a recorder that reverses what it is given.

    Reversing matters: if the retriever ever stopped using the return value, an
    order-preserving stub would let these assertions pass anyway.
    """
    calls: list[dict] = []

    async def fake_rerank_documents(query, hits, top_n):
        calls.append({"query": query, "hits": hits, "top_n": top_n})
        return hits[::-1][:top_n]

    monkeypatch.setattr(policy_retriever, "rerank_documents", fake_rerank_documents)
    return calls


@ALL_MODES
async def test_rerank_off_never_calls_the_reranker(monkeypatch, retrieve, expected_mode) -> None:
    hits = _canned_hits()
    _install_stub(monkeypatch, hits)
    calls = _install_rerank_stub(monkeypatch)

    assert await retrieve("warranty period", rerank=False) == hits
    assert calls == []


@ALL_MODES
async def test_rerank_on_passes_the_whole_pool_through(
    monkeypatch, retrieve, expected_mode
) -> None:
    hits = _canned_hits()
    _install_stub(monkeypatch, hits)
    calls = _install_rerank_stub(monkeypatch)

    result = await retrieve("warranty period", rerank=True, top_n=1)

    assert len(calls) == 1
    assert calls[0]["query"] == "warranty period"
    # The reranker sees every candidate, not a pre-truncated slice.
    assert calls[0]["hits"] == hits
    assert calls[0]["top_n"] == 1
    assert result == [hits[-1]]


@ALL_MODES
async def test_rerank_narrows_after_the_fetch_not_instead_of_it(
    monkeypatch, retrieve, expected_mode
) -> None:
    # The whole point of the two-stage split: recall comes from the wide `k`, so
    # `top_n` must never be what reaches Qdrant.
    store = _install_stub(monkeypatch, _canned_hits())
    _install_rerank_stub(monkeypatch)

    await retrieve("warranty period", k=20, rerank=True, top_n=5)

    assert store.calls[0]["k"] == 20
