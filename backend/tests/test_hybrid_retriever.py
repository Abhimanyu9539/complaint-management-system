from qdrant_client import models

from cms.retrieval.retrievers import hybrid_retriever
from cms.retrieval.retrievers.base import RetrievedChunk, to_chunk
from cms.retrieval.retrievers.hybrid_retriever import (
    RRF_K,
    RetrievalResult,
    build_filter,
    retrieve,
    rrf_fuse,
)


def _chunk(point_id: str, *, corpus: str = "case", score: float = 0.0) -> RetrievedChunk:
    return RetrievedChunk(
        point_id=point_id,
        chunk_id=f"chunk-{point_id}",
        doc_id=f"doc-{point_id}",
        corpus=corpus,
        text=f"text for {point_id}",
        title=f"title {point_id}",
        department="warranty",
        score=score,
    )


class _FakeDocument:
    def __init__(self, page_content: str, metadata: dict) -> None:
        self.page_content = page_content
        self.metadata = metadata


# ---------------------------------------------------------------------------
# rrf_fuse
# ---------------------------------------------------------------------------


def test_rrf_fuse_consistent_across_lists_beats_single_list_top() -> None:
    # "consistent" ranks #2 in both lists; "single-top" ranks #1 in only one.
    list_a = [_chunk("single-top"), _chunk("consistent")]
    list_b = [_chunk("other"), _chunk("consistent")]

    fused = rrf_fuse([list_a, list_b], k=10)

    assert fused[0].point_id == "consistent"


def test_rrf_fuse_multi_variant_outranks_single_variant_same_rank() -> None:
    # "two_variants" appears at rank 0 in two lists; "one_variant" at rank 0 in
    # only one — the former must win even though both rank #1 somewhere.
    list_a = [_chunk("two_variants")]
    list_b = [_chunk("two_variants")]
    list_c = [_chunk("one_variant")]

    fused = rrf_fuse([list_a, list_b, list_c], k=10)

    assert fused[0].point_id == "two_variants"


def test_rrf_fuse_dedupes_by_point_id() -> None:
    fused = rrf_fuse([[_chunk("x")], [_chunk("x")], [_chunk("x")]], k=10)

    assert [c.point_id for c in fused] == ["x"]


def test_rrf_fuse_respects_k() -> None:
    ranked = [_chunk(str(i)) for i in range(5)]

    fused = rrf_fuse([ranked], k=2)

    assert len(fused) == 2


def test_rrf_fuse_score_is_reciprocal_rank_sum() -> None:
    fused = rrf_fuse([[_chunk("x")], [_chunk("x")]], k=10)

    assert fused[0].score == 2 / RRF_K


# ---------------------------------------------------------------------------
# build_filter
# ---------------------------------------------------------------------------


def test_build_filter_none_when_nothing_to_filter() -> None:
    assert build_filter(None) is None
    assert build_filter([]) is None


def test_build_filter_uses_dotted_metadata_path() -> None:
    filt = build_filter(["warranty"])

    assert filt.must[0].key == "metadata.department"


def test_build_filter_match_value_for_one_department() -> None:
    filt = build_filter(["warranty"])

    assert isinstance(filt.must[0].match, models.MatchValue)
    assert filt.must[0].match.value == "warranty"


def test_build_filter_match_any_for_several_departments() -> None:
    filt = build_filter(["warranty", "returns"])

    assert isinstance(filt.must[0].match, models.MatchAny)
    assert filt.must[0].match.any == ["warranty", "returns"]


def test_build_filter_lifecycle_only_when_published_only() -> None:
    without = build_filter(["warranty"], published_only=False)
    with_ = build_filter(["warranty"], published_only=True)

    assert not any(c.key == "metadata.lifecycle" for c in without.must)
    lifecycle_conditions = [c for c in with_.must if c.key == "metadata.lifecycle"]
    assert len(lifecycle_conditions) == 1
    assert lifecycle_conditions[0].match.value == "published"


def test_build_filter_lifecycle_alone_still_filters() -> None:
    filt = build_filter(None, published_only=True)

    assert filt is not None
    assert filt.must[0].key == "metadata.lifecycle"


# ---------------------------------------------------------------------------
# to_chunk
# ---------------------------------------------------------------------------


def test_to_chunk_tolerates_missing_metadata() -> None:
    doc = _FakeDocument("some text", {"_id": "p1"})

    chunk = to_chunk(doc, 0.5, "case")

    assert chunk.point_id == "p1"
    assert chunk.title is None
    assert chunk.department is None
    assert chunk.doc_id is None


def test_to_chunk_reads_expected_fields() -> None:
    doc = _FakeDocument(
        "some text",
        {"_id": "p1", "doc_id": "d1", "title": "T", "department": "warranty", "chunk_id": "c1"},
    )

    chunk = to_chunk(doc, 0.9, "policy")

    assert chunk.doc_id == "d1"
    assert chunk.title == "T"
    assert chunk.department == "warranty"
    assert chunk.chunk_id == "c1"
    assert chunk.corpus == "policy"
    assert chunk.score == 0.9


# ---------------------------------------------------------------------------
# retrieve() — both legs, both corpora, their distinct filters
# ---------------------------------------------------------------------------


class _FakeSettings:
    qdrant_cases_collection = "cases_v1"
    qdrant_policies_collection = "policies_v1"


def test_retrieve_consults_both_legs_and_both_corpora(monkeypatch) -> None:
    calls: list[tuple] = []

    def fake_dense(collection_name, query, corpus, k, query_filter):
        calls.append(("dense", collection_name, corpus, query_filter))
        return [_chunk(f"dense-{corpus}", corpus=corpus)]

    def fake_sparse(collection_name, query, corpus, k, query_filter):
        calls.append(("sparse", collection_name, corpus, query_filter))
        return [_chunk(f"sparse-{corpus}", corpus=corpus)]

    monkeypatch.setattr(hybrid_retriever, "dense_search", fake_dense)
    monkeypatch.setattr(hybrid_retriever, "sparse_search", fake_sparse)
    monkeypatch.setattr(hybrid_retriever, "get_settings", lambda: _FakeSettings())

    result: RetrievalResult = retrieve("some query", departments=["warranty"])

    legs_seen = {c[0] for c in calls}
    corpora_seen = {c[2] for c in calls}
    assert legs_seen == {"dense", "sparse"}
    assert corpora_seen == {"case", "policy"}

    # A chunk only the sparse leg found still survives into the final result —
    # the behavioural reason hybrid retrieval exists.
    assert {c.point_id for c in result.cases} == {"dense-case", "sparse-case"}
    assert {c.point_id for c in result.policies} == {"dense-policy", "sparse-policy"}


def test_retrieve_cases_filter_has_no_lifecycle_condition(monkeypatch) -> None:
    filters_by_corpus: dict[str, models.Filter] = {}

    def fake_dense(collection_name, query, corpus, k, query_filter):
        filters_by_corpus[corpus] = query_filter
        return []

    monkeypatch.setattr(hybrid_retriever, "dense_search", fake_dense)
    monkeypatch.setattr(hybrid_retriever, "sparse_search", fake_dense)
    monkeypatch.setattr(hybrid_retriever, "get_settings", lambda: _FakeSettings())

    retrieve("q", departments=["warranty"])

    case_keys = {c.key for c in filters_by_corpus["case"].must}
    policy_keys = {c.key for c in filters_by_corpus["policy"].must}
    assert "metadata.lifecycle" not in case_keys
    assert "metadata.lifecycle" in policy_keys


def test_retrieve_normalizes_string_query_and_drops_blanks(monkeypatch) -> None:
    seen_queries: list[str] = []

    def fake_search(collection_name, query, corpus, k, query_filter):
        seen_queries.append(query)
        return []

    monkeypatch.setattr(hybrid_retriever, "dense_search", fake_search)
    monkeypatch.setattr(hybrid_retriever, "sparse_search", fake_search)
    monkeypatch.setattr(hybrid_retriever, "get_settings", lambda: _FakeSettings())

    result = retrieve(["  same query  ", "", "same query", "  "])

    assert result.queries == ["same query"]
    assert seen_queries.count("same query") == 4  # 2 legs x 2 corpora, one query variant


def test_retrieve_raises_on_all_blank_query() -> None:
    try:
        retrieve(["", "   "])
    except ValueError:
        return
    raise AssertionError("expected ValueError for an all-blank query")
