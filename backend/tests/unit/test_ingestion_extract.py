from pathlib import Path

import pytest

from cms.ingestion.extract.cases_extractor import build_case_text, load_seed_cases
from cms.ingestion.extract.policy_extractor import parse_frontmatter, read_policy_file


def test_json_loader_emits_structured_case_records(tmp_path: Path) -> None:
    path = tmp_path / "cases.json"
    path.write_text(
        """[
          {
            "id": "C-1",
            "department": "billing",
            "category": "duplicate_charge",
            "resolution_path": "direct",
            "complaint_text": "Charged twice.",
            "dept_guidance": null,
            "resolution_text": "Refunded the duplicate."
          }
        ]""",
        encoding="utf-8",
    )

    cases = load_seed_cases(path)

    assert cases == [
        {
            "id": "C-1",
            "department": "billing",
            "category": "duplicate_charge",
            "resolution_path": "direct",
            "complaint_text": "Charged twice.",
            "dept_guidance": None,
            "resolution_text": "Refunded the duplicate.",
        }
    ]
    assert build_case_text(cases[0]) == (
        "COMPLAINT:\nCharged twice.\n\n"
        "RESOLUTION:\nRefunded the duplicate."
    )


def test_json_loader_preserves_optional_department_guidance(tmp_path: Path) -> None:
    path = tmp_path / "cases.json"
    path.write_text(
        """[{
          "id": "C-2",
          "department": "warranty",
          "category": "safety",
          "resolution_path": "escalated",
          "complaint_text": "It smoked.",
          "dept_guidance": "Stop use and refund.",
          "resolution_text": "Refunded."
        }]""",
        encoding="utf-8",
    )

    case = load_seed_cases(path)[0]

    assert case["dept_guidance"] == "Stop use and refund."
    assert "DEPARTMENT GUIDANCE:\nStop use and refund." in build_case_text(case)


def test_json_loader_rejects_missing_case_fields(tmp_path: Path) -> None:
    path = tmp_path / "cases.json"
    path.write_text('[{"id": "C-3"}]', encoding="utf-8")

    with pytest.raises(ValueError, match="missing required field"):
        load_seed_cases(path)


def test_text_loader_reads_utf8_policy_and_strips_frontmatter(tmp_path: Path) -> None:
    path = tmp_path / "returns-policy.md"
    path.write_text(
        "---\ndepartment: returns\ntitle: Returns Policy\n---\n\n# Returns\n\n"
        "Refunds are \u20b91,500.\n",
        encoding="utf-8",
    )

    metadata, body = read_policy_file(path)

    assert metadata == {"department": "returns", "title": "Returns Policy"}
    assert body == "# Returns\n\nRefunds are \u20b91,500.\n"


@pytest.mark.parametrize(
    ("markdown", "expected_metadata", "expected_body"),
    [
        ("# Body\n", {}, "# Body\n"),
        ("---\ntitle: Incomplete\n# Body\n", {}, "---\ntitle: Incomplete\n# Body\n"),
    ],
)
def test_frontmatter_edge_cases(
    markdown: str,
    expected_metadata: dict[str, str],
    expected_body: str,
) -> None:
    assert parse_frontmatter(markdown) == (expected_metadata, expected_body)

