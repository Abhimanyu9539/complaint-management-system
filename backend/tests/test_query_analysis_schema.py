from cms.schemas.query_analysis import DepartmentCandidate, QueryAnalysis


def _analysis(*candidates: tuple[str, float]) -> QueryAnalysis:
    return QueryAnalysis(
        intent="complaint_query",
        department_candidates=[
            DepartmentCandidate(department=dept, confidence=conf) for dept, conf in candidates
        ],
    )


def test_out_of_order_candidates_are_sorted_by_confidence() -> None:
    analysis = _analysis(("returns", 0.2), ("warranty", 0.9))

    assert [c.department for c in analysis.department_candidates] == ["warranty", "returns"]


def test_department_and_confidence_read_the_top_candidate() -> None:
    analysis = _analysis(("returns", 0.2), ("warranty", 0.9))

    assert analysis.department == "warranty"
    assert analysis.dept_confidence == 0.9


def test_department_defaults_are_none_and_zero_impossible_without_a_candidate() -> None:
    # min_length=1 means QueryAnalysis can never actually be built with zero
    # candidates — this documents that the properties are still safe if that
    # constraint is ever loosened.
    analysis = _analysis(("warranty", 0.5))
    object.__setattr__(analysis, "department_candidates", [])

    assert analysis.department is None
    assert analysis.dept_confidence == 0.0
