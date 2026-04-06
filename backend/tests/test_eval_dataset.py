import json

import pytest

from cms.evals import dataset as dataset_module
from cms.evals.dataset import (
    COMPANY_WIDE,
    EvalContext,
    _sample_evenly,
    annotate_goldens,
    parse_header,
    select_stratified,
    write_contexts_file,
)


def _context(source_ref: str, department: str | None, corpus: str = "policy") -> EvalContext:
    return EvalContext(
        source_ref=source_ref,
        corpus=corpus,
        department=department,
        title="Some Title",
        chunks=["first chunk", "second chunk"],
    )


def test_header_round_trips_for_a_department_policy() -> None:
    context = _context("warranty-policy.md", "warranty")

    assert parse_header(context.to_context()[0]) == {
        "corpus": "policy",
        "source_ref": "warranty-policy.md",
        "expected_department": "warranty",
        "title": "Some Title",
    }


def test_company_wide_policy_round_trips_back_to_none() -> None:
    """NULL department means "applies to every department", not "missing"."""
    context = _context("escalation-policy.md", None)

    assert COMPANY_WIDE in context.header()
    assert parse_header(context.to_context()[0])["expected_department"] is None


def test_case_header_round_trips() -> None:
    context = EvalContext(
        source_ref="C-1001",
        corpus="case",
        department="warranty",
        title="faulty_product",
        chunks=["COMPLAINT:\nIt broke.\n\nRESOLUTION:\nReplaced it."],
    )

    parsed = parse_header(context.to_context()[0])

    assert parsed["corpus"] == "case"
    assert parsed["source_ref"] == "C-1001"
    assert parsed["title"] == "faulty_product"


def test_header_lands_on_the_first_chunk_only() -> None:
    chunks = _context("warranty-policy.md", "warranty").to_context()

    assert chunks[0].endswith("first chunk")
    assert chunks[1] == "second chunk"
    assert parse_header(chunks[1]) is None


def test_unparseable_chunk_yields_none() -> None:
    assert parse_header("just some policy prose") is None
    assert parse_header("") is None


def test_sample_evenly_spreads_across_the_document() -> None:
    items = [f"chunk-{index}" for index in range(9)]

    assert _sample_evenly(items, 3) == ["chunk-0", "chunk-3", "chunk-6"]
    # Fewer items than the limit is not an error — short policies exist.
    assert _sample_evenly(["only"], 3) == ["only"]


def test_select_stratified_covers_departments_before_repeating() -> None:
    contexts = [
        _context("billing-a.md", "billing"),
        _context("billing-b.md", "billing"),
        _context("billing-c.md", "billing"),
        _context("warranty-a.md", "warranty"),
        _context("returns-a.md", "returns"),
    ]

    selected = select_stratified(contexts, 3)

    assert {c.department for c in selected} == {"billing", "warranty", "returns"}


def test_select_stratified_is_deterministic() -> None:
    contexts = [_context(f"p-{index}.md", f"dept-{index % 3}") for index in range(9)]

    assert [c.source_ref for c in select_stratified(contexts, 4)] == [
        c.source_ref for c in select_stratified(contexts, 4)
    ]


def test_select_stratified_passes_through_when_limit_is_none() -> None:
    contexts = [_context("a.md", "billing"), _context("b.md", "warranty")]

    assert select_stratified(contexts, None) == contexts


def test_write_contexts_file_shape(tmp_path) -> None:
    path = tmp_path / "contexts.json"

    count = write_contexts_file([_context("warranty-policy.md", "warranty")], path)

    payload = json.loads(path.read_text(encoding="utf-8"))
    assert count == 1
    assert isinstance(payload, list)
    assert isinstance(payload[0], list)
    assert all(isinstance(chunk, str) for chunk in payload[0])


def test_write_contexts_file_refuses_an_empty_selection(tmp_path) -> None:
    with pytest.raises(ValueError):
        write_contexts_file([], tmp_path / "contexts.json")


def test_annotate_attaches_ground_truth(tmp_path) -> None:
    context = _context("warranty-policy.md", "warranty").to_context()
    generated = tmp_path / "generated.json"
    generated.write_text(
        json.dumps(
            [
                {
                    "input": "My X200 stopped charging.",
                    "actual_output": None,
                    "expected_output": "Covered under warranty §2.3.",
                    "context": context,
                    "source_file": None,
                }
            ]
        ),
        encoding="utf-8",
    )
    out = tmp_path / ".dataset.json"

    assert annotate_goldens(generated, out) == 1

    golden = json.loads(out.read_text(encoding="utf-8"))[0]
    assert golden["source_file"] == "warranty-policy.md"
    assert golden["additional_metadata"]["corpus"] == "policy"
    assert golden["additional_metadata"]["expected_department"] == "warranty"
    assert golden["input"] == "My X200 stopped charging."


def test_annotate_keeps_a_golden_whose_source_cannot_be_resolved(tmp_path, caplog) -> None:
    """Silently shrinking the dataset is worse than a flagged row."""
    generated = tmp_path / "generated.json"
    generated.write_text(
        json.dumps([{"input": "orphan", "context": ["no header here"]}]),
        encoding="utf-8",
    )
    out = tmp_path / ".dataset.json"

    with caplog.at_level("WARNING"):
        assert annotate_goldens(generated, out) == 1

    golden = json.loads(out.read_text(encoding="utf-8"))[0]
    assert golden["source_file"] is None
    assert golden["additional_metadata"]["source_ref"] is None
    assert "no parseable source header" in caplog.text


def test_annotate_rejects_an_empty_generation(tmp_path) -> None:
    generated = tmp_path / "generated.json"
    generated.write_text("[]", encoding="utf-8")

    with pytest.raises(ValueError):
        annotate_goldens(generated, tmp_path / ".dataset.json")


def test_build_contexts_stratifies_each_corpus_separately(monkeypatch) -> None:
    """A shared budget would let 34 policies crowd out the 20 cases."""
    monkeypatch.setattr(
        dataset_module,
        "build_policy_contexts",
        lambda: [_context(f"p-{index}.md", f"dept-{index}") for index in range(5)],
    )
    monkeypatch.setattr(
        dataset_module,
        "build_case_contexts",
        lambda: [_context(f"C-{index}", f"dept-{index}", corpus="case") for index in range(5)],
    )

    contexts = dataset_module.build_contexts(policy_limit=2, case_limit=3)

    assert [c.corpus for c in contexts] == ["policy", "policy", "case", "case", "case"]
