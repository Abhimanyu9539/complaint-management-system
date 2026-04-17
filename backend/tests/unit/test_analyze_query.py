from cms.rag.nodes import analyze_query as analyze_query_module
from cms.schemas.query_analysis import DepartmentCandidate, QueryAnalysis


def _canned_analysis() -> QueryAnalysis:
    return QueryAnalysis(
        intent="complaint_query",
        department_candidates=[
            DepartmentCandidate(department="warranty", confidence=0.9),
            DepartmentCandidate(department="returns", confidence=0.3),
        ],
        entities={"product": "X200"},
        search_queries=["X200 charging failure"],
    )


async def test_analyze_query_node_maps_analysis_onto_partial_state(monkeypatch) -> None:
    async def fake_core(query: str) -> QueryAnalysis:
        return _canned_analysis()

    monkeypatch.setattr(analyze_query_module, "analyze_query_core", fake_core)

    update = await analyze_query_module.analyze_query({"query": "my X200 won't charge"})

    assert update["intent"] == "complaint_query"
    assert update["department"] == "warranty"
    assert update["dept_confidence"] == 0.9
    assert update["department_candidates"] == [
        {"department": "warranty", "confidence": 0.9},
        {"department": "returns", "confidence": 0.3},
    ]
    assert update["entities"] == {"product": "X200"}
    assert update["search_queries"] == ["X200 charging failure"]


async def test_analyze_query_node_passes_state_query_through(monkeypatch) -> None:
    seen_queries: list[str] = []

    async def fake_core(query: str) -> QueryAnalysis:
        seen_queries.append(query)
        return _canned_analysis()

    monkeypatch.setattr(analyze_query_module, "analyze_query_core", fake_core)

    await analyze_query_module.analyze_query({"query": "a specific complaint"})

    assert seen_queries == ["a specific complaint"]


async def test_department_prompt_block_formats_id_name_description(monkeypatch) -> None:
    analyze_query_module.reset_department_prompt_block()

    async def fake_descriptions() -> list[dict]:
        return [{"id": "warranty", "name": "Warranty", "description": "Coverage and claims."}]

    monkeypatch.setattr(
        analyze_query_module, "list_department_descriptions", fake_descriptions
    )

    block = await analyze_query_module._department_prompt_block()

    assert block == "- warranty (Warranty): Coverage and claims."
    analyze_query_module.reset_department_prompt_block()
