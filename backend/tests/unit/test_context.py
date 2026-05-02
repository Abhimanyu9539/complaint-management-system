from langchain_core.documents import Document

from cms.rag.context import build_context

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
