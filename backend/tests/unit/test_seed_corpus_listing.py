import json

import pytest

from cms.ingestion import seed


def _write_policy(directory, filename: str, *, title: str | None = None, body: str = "Body text.") -> None:
    frontmatter = f"---\ntitle: {title}\n---\n" if title is not None else ""
    (directory / filename).write_text(frontmatter + body, encoding="utf-8")


def _write_cases(path, cases: list[dict]) -> None:
    path.write_text(json.dumps(cases), encoding="utf-8")


def _case_record(case_id: str, **overrides) -> dict:
    record = {
        "id": case_id,
        "department": "warranty",
        "category": "defect",
        "resolution_path": "self_service",
        "complaint_text": "The unit stopped working.",
        "dept_guidance": None,
        "resolution_text": "Replaced under warranty.",
    }
    record.update(overrides)
    return record


@pytest.fixture
def seed_dir(tmp_path, monkeypatch):
    (tmp_path / "policies").mkdir()
    monkeypatch.setattr(seed, "resolve_seed_dir", lambda: tmp_path)
    return tmp_path


def test_find_seed_policy_rejects_a_traversal_source_ref(seed_dir) -> None:
    """Regression test: `source_ref` is client input on an unauthenticated
    route, so resolution must never join it onto a filesystem path — only
    match it against the enumerated directory listing."""
    _write_policy(seed_dir / "policies", "warranty-policy.md", title="Warranty Policy")
    secret = seed_dir.parent / "secret.txt"
    secret.write_text("do not read this", encoding="utf-8")

    with pytest.raises(LookupError):
        seed.find_seed_policy("../secret.txt")
    with pytest.raises(LookupError):
        seed.find_seed_policy(str(secret))
    with pytest.raises(LookupError):
        seed.find_seed_policy("/etc/passwd")

    resolved = seed.find_seed_policy("warranty-policy.md")
    assert resolved.name == "warranty-policy.md"


def test_find_seed_case_rejects_an_unknown_id(seed_dir) -> None:
    _write_cases(seed_dir / "cases.json", [_case_record("C-1001")])

    with pytest.raises(LookupError):
        seed.find_seed_case("C-9999")

    found = seed.find_seed_case("C-1001")
    assert found["id"] == "C-1001"


def test_case_entry_title_matches_what_register_seed_case_writes(seed_dir) -> None:
    case = _case_record("C-1001", department="billing", category="refund")
    _write_cases(seed_dir / "cases.json", [case])

    entries = seed.list_seed_entries("case")

    assert len(entries) == 1
    assert entries[0].source_ref == "C-1001"
    assert entries[0].title == seed.case_title(case)


def test_policy_entry_source_ref_is_the_filename(seed_dir) -> None:
    _write_policy(seed_dir / "policies", "warranty-policy.md", title="Warranty Policy")

    entries = seed.list_seed_entries("policy")

    assert len(entries) == 1
    assert entries[0].source_ref == "warranty-policy.md"
    assert entries[0].title == "Warranty Policy"


def test_an_unreadable_policy_file_still_lists_with_its_stem_as_title(seed_dir, monkeypatch) -> None:
    _write_policy(seed_dir / "policies", "good-policy.md", title="Good Policy")
    _write_policy(seed_dir / "policies", "bad-policy.md", title="Bad Policy")

    original_read = seed.read_policy_file

    def flaky_read(path):
        if path.name == "bad-policy.md":
            raise ValueError("could not decode file")
        return original_read(path)

    monkeypatch.setattr(seed, "read_policy_file", flaky_read)

    entries = seed.list_seed_entries("policy")

    by_ref = {entry.source_ref: entry.title for entry in entries}
    assert by_ref["good-policy.md"] == "Good Policy"
    assert by_ref["bad-policy.md"] == "bad-policy"  # falls back to the filename stem


def test_a_malformed_cases_file_raises(seed_dir) -> None:
    (seed_dir / "cases.json").write_text("not valid json", encoding="utf-8")

    with pytest.raises(Exception):
        seed.list_seed_entries("case")
