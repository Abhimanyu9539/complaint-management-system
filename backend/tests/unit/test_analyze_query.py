from cms.rag.nodes import analyze_query as analyze_query_module
from cms.schemas.query_analysis import QueryAnalysis


def _canned_analysis() -> QueryAnalysis:
    return QueryAnalysis(
        intent="complaint_query",
        policy_queries=[
            "limited warranty coverage period defect eligibility",
            "replacement versus repair remedy under warranty",
        ],
    )


async def test_analyze_query_node_prepends_the_original_query(monkeypatch) -> None:
    async def fake_core(query: str) -> QueryAnalysis:
        return _canned_analysis()

    monkeypatch.setattr(analyze_query_module, "analyze_query_core", fake_core)

    update = await analyze_query_module.analyze_query({"query": "my X200 won't charge"})

    assert update["intent"] == "complaint_query"
    assert update["policy_queries"] == [
        "my X200 won't charge",
        "limited warranty coverage period defect eligibility",
        "replacement versus repair remedy under warranty",
    ]


async def test_analyze_query_node_passes_state_query_through(monkeypatch) -> None:
    seen_queries: list[str] = []

    async def fake_core(query: str) -> QueryAnalysis:
        seen_queries.append(query)
        return _canned_analysis()

    monkeypatch.setattr(analyze_query_module, "analyze_query_core", fake_core)

    await analyze_query_module.analyze_query({"query": "a specific complaint"})

    assert seen_queries == ["a specific complaint"]


def test_build_policy_queries_is_empty_for_smalltalk() -> None:
    analysis = QueryAnalysis(intent="smalltalk_or_meta")

    assert analyze_query_module.build_policy_queries("hey there", analysis) == []
