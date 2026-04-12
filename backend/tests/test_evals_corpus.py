"""Offline tests for the eval build's non-LLM halves.

Everything here is free: `corpus` only touches the filesystem, and `build._record`
is pure data joining. The paid parts (`build.generate`, `build._gate`) are not
exercised — `tests/evals/` is where money gets spent, and `norecursedirs` keeps
it out of a bare `pytest` run.
"""

import json
from pathlib import Path
from types import SimpleNamespace

import pytest

from cms.evals import corpus as corpus_module
from cms.evals.build import _record
from cms.evals.corpus import SourceDoc, materialize_corpus

CASE = {
    "id": "C-1001",
    "department": "warranty",
    "category": "faulty_product",
    "resolution_path": "replacement",
    "complaint_text": "My X200 stopped charging.",
    "dept_guidance": None,
    "resolution_text": "Replaced under warranty.",
}

POLICY = """---
department: warranty
title: Product Warranty Policy
version: "1.0"
---

# Product Warranty Policy

Covered for 24 months from delivery.
"""


@pytest.fixture
def seed(tmp_path, monkeypatch):
    """A two-document seed corpus on disk, wired into `resolve_seed_dir`."""
    seed_dir = tmp_path / "seed"
    (seed_dir / "policies").mkdir(parents=True)
    (seed_dir / "policies" / "warranty-policy.md").write_text(POLICY, encoding="utf-8")
    (seed_dir / "cases.json").write_text(json.dumps([CASE]), encoding="utf-8")
    monkeypatch.setattr(corpus_module, "resolve_seed_dir", lambda: seed_dir)
    return seed_dir


def test_materialize_writes_one_document_per_source(seed, tmp_path):
    index = materialize_corpus(tmp_path / "docs")

    assert set(index) == {"warranty-policy.md", "C-1001.md"}
    assert all(doc.path.exists() for doc in index.values())


def test_policy_frontmatter_is_stripped(seed, tmp_path):
    """Left in, the generator writes goldens about `version:` and `title:`."""
    index = materialize_corpus(tmp_path / "docs")
    body = index["warranty-policy.md"].path.read_text(encoding="utf-8")

    assert "Covered for 24 months" in body
    assert "---" not in body
    assert "version:" not in body


def test_case_document_holds_exactly_the_embedded_text(seed, tmp_path):
    """The golden must be grounded in the text that is actually in Qdrant."""
    from cms.ingestion.extract.cases_extractor import build_case_text

    index = materialize_corpus(tmp_path / "docs")

    assert index["C-1001.md"].path.read_text(encoding="utf-8") == build_case_text(CASE)


def test_ground_truth_survives_the_round_trip(seed, tmp_path):
    index = materialize_corpus(tmp_path / "docs")

    policy = index["warranty-policy.md"]
    assert (policy.source_ref, policy.corpus, policy.department) == (
        "warranty-policy.md",
        "policy",
        "warranty",
    )
    assert policy.title == "Product Warranty Policy"

    case = index["C-1001.md"]
    assert (case.source_ref, case.corpus, case.department) == (
        "C-1001",
        "case",
        "warranty",
    )
    # Must equal what `register_seed_case` writes to the Qdrant payload, or
    # `verify` cannot recognise a retrieved chunk as this case.
    assert case.title == "C-1001 — warranty / faulty_product"


def test_company_wide_policy_has_no_department(tmp_path, monkeypatch):
    """Frontmatter omits `department` entirely; NULL means "every department"."""
    seed_dir = tmp_path / "seed"
    (seed_dir / "policies").mkdir(parents=True)
    (seed_dir / "policies" / "escalation-policy.md").write_text(
        "---\ntitle: Escalation Policy\n---\n\nBody.\n", encoding="utf-8"
    )
    (seed_dir / "cases.json").write_text("[]", encoding="utf-8")
    monkeypatch.setattr(corpus_module, "resolve_seed_dir", lambda: seed_dir)

    index = materialize_corpus(tmp_path / "docs")

    assert index["escalation-policy.md"].department is None


def test_materialize_rejects_an_empty_corpus(tmp_path, monkeypatch):
    seed_dir = tmp_path / "seed"
    (seed_dir / "policies").mkdir(parents=True)
    (seed_dir / "cases.json").write_text("[]", encoding="utf-8")
    monkeypatch.setattr(corpus_module, "resolve_seed_dir", lambda: seed_dir)

    with pytest.raises(ValueError):
        materialize_corpus(tmp_path / "docs")


def _golden(**overrides):
    defaults = {
        "input": "My X200 stopped charging. Am I covered?",
        "expected_output": "Yes — covered for 24 months (warranty §1).",
        "context": ["Covered for 24 months from delivery."],
        "source_file": str(Path("docs") / "warranty-policy.md"),
        "additional_metadata": {"context_quality": 0.9, "synthetic_input_quality": 0.8},
    }
    return SimpleNamespace(**{**defaults, **overrides})


@pytest.fixture
def index():
    return {
        "warranty-policy.md": SourceDoc(
            source_ref="warranty-policy.md",
            corpus="policy",
            department="warranty",
            title="Product Warranty Policy",
            path=Path("docs/warranty-policy.md"),
        )
    }


def test_record_joins_ground_truth_by_filename(index):
    """No header line, no regex — `source_file` maps straight back."""
    record = _record(_golden(), index)

    assert record["source_file"] == "warranty-policy.md"
    assert record["additional_metadata"]["corpus"] == "policy"
    assert record["additional_metadata"]["expected_department"] == "warranty"
    assert record["additional_metadata"]["title"] == "Product Warranty Policy"
    # deepeval's own critic scores are carried through, not recomputed.
    assert record["additional_metadata"]["context_quality"] == 0.9


def test_record_drops_a_golden_with_no_resolvable_source(index, caplog):
    with caplog.at_level("WARNING"):
        assert _record(_golden(source_file="docs/not-in-corpus.md"), index) is None
    assert "not in the corpus index" in caplog.text


def test_record_carries_deepeval_critic_scores_through(index):
    """Scores deepeval already computed; recomputing them would cost tokens."""
    record = _record(_golden(), index)

    assert record["additional_metadata"]["context_quality"] == 0.9
    assert record["additional_metadata"]["synthetic_input_quality"] == 0.8
