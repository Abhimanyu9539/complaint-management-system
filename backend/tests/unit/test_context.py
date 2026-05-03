from langchain_core.documents import Document

from cms.rag.context import build_context, used_citations
from cms.schemas.generation import Citation

BREADCRUMB = "Warranty Policy > 2. Manufacturing Defects > 2.3 Charging Circuit"


def _hit(chunk_id: str, score: float = 0.9, body: str = "body text") -> tuple[Document, float]:
    """A chunk shaped the way ingestion writes them: breadcrumb, then body."""
    return (
        Document(
            page_content=f"{BREADCRUMB}\n\n{body}",
            metadata={
                "doc_id": "doc-1",
                "chunk_id": chunk_id,
                "title": "Warranty Policy",
            },
        ),
        score,
    )


def test_markers_are_sequential_and_preserve_rank_order() -> None:
    context, citations = build_context([_hit("c1"), _hit("c2"), _hit("c3")])

    assert [citation.marker for citation in citations] == [1, 2, 3]
    assert [citation.chunk_id for citation in citations] == ["c1", "c2", "c3"]
    # The markers appear in the block in the same order the model will read them.
    assert context.index("[1]") < context.index("[2]") < context.index("[3]")


def test_citations_line_up_with_the_blocks() -> None:
    context, citations = build_context([_hit("c1"), _hit("c2")])

    assert len(citations) == context.count("[")  # one marker per citation
    for citation in citations:
        assert f"[{citation.marker}] {citation.title}" in context


def test_section_is_the_breadcrumb_line() -> None:
    _, citations = build_context([_hit("c1")])

    assert citations[0].section == BREADCRUMB


def test_budget_keeps_a_prefix_and_drops_the_rest() -> None:
    hits = [_hit(f"c{i}", body="word " * 200) for i in range(5)]

    # Small enough that only the first chunk or two can fit.
    context, citations = build_context(hits, budget_tokens=250)

    assert 0 < len(citations) < len(hits)
    # Whole chunks only — nothing is cut mid-clause.
    assert context.count("[") == len(citations)
    assert [citation.marker for citation in citations] == list(
        range(1, len(citations) + 1)
    )


def test_a_chunk_larger_than_the_budget_yields_nothing() -> None:
    context, citations = build_context([_hit("c1", body="word " * 500)], budget_tokens=10)

    assert (context, citations) == ("", [])


def test_no_hits_is_an_empty_context() -> None:
    assert build_context([]) == ("", [])


def test_missing_metadata_does_not_raise() -> None:
    """A hand-built Document in a probe need not carry ingestion's payload."""
    bare = (Document(page_content="just text"), 0.5)

    context, citations = build_context([bare])

    assert citations[0].title == "Untitled"
    assert citations[0].doc_id == ""
    assert citations[0].section == "just text"
    assert "[1] Untitled" in context


# --- used_citations -------------------------------------------------------


def _citations(count: int) -> list[Citation]:
    return [
        Citation(
            marker=marker,
            doc_id="doc-1",
            chunk_id=f"c{marker}",
            title="Warranty Policy",
            section="Warranty Policy > 2.3 Defects",
        )
        for marker in range(1, count + 1)
    ]


def test_only_cited_markers_are_kept() -> None:
    kept = used_citations("Covered [1], remedy is replacement [3].", _citations(4))

    assert [citation.marker for citation in kept] == [1, 3]


def test_kept_citations_are_in_marker_order() -> None:
    """Cited out of order in the prose; presented in order to the agent."""
    kept = used_citations("Replacement [3] applies because it is covered [1].", _citations(4))

    assert [citation.marker for citation in kept] == [1, 3]


def test_a_marker_cited_twice_is_returned_once() -> None:
    kept = used_citations("Covered [1] and still covered [1].", _citations(2))

    assert [citation.marker for citation in kept] == [1]


def test_a_draft_citing_nothing_returns_nothing() -> None:
    assert used_citations("Covered under the warranty.", _citations(4)) == []


def test_a_fabricated_marker_is_dropped_without_raising() -> None:
    kept = used_citations("Covered [1] under clause [15].", _citations(4))

    assert [citation.marker for citation in kept] == [1]


def test_no_citations_to_filter() -> None:
    assert used_citations("anything [1]", []) == []
