from langchain_core.messages import AIMessage, HumanMessage
from langchain_core.runnables import RunnableLambda

from cms.rag.nodes import analyze_query as analyze_query_module
from cms.schemas.query_analysis import QueryAnalysis, TurnAnalysis


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


async def test_any_risk_flag_requires_lead_review(monkeypatch) -> None:
    async def fake_core(query: str) -> QueryAnalysis:
        return QueryAnalysis(intent="complaint_query", risk_flags=["safety", "legal"])

    monkeypatch.setattr(analyze_query_module, "analyze_query_core", fake_core)

    update = await analyze_query_module.analyze_query({"query": "it sparked and burned me"})

    assert update["risk_flags"] == ["safety", "legal"]
    assert update["requires_lead_review"] is True


async def test_no_risk_flags_needs_no_lead_review(monkeypatch) -> None:
    async def fake_core(query: str) -> QueryAnalysis:
        return _canned_analysis()

    monkeypatch.setattr(analyze_query_module, "analyze_query_core", fake_core)

    update = await analyze_query_module.analyze_query({"query": "my X200 won't charge"})

    assert update["risk_flags"] == []
    assert update["requires_lead_review"] is False


def test_build_policy_queries_prepends_the_original_for_a_lookup() -> None:
    analysis = QueryAnalysis(
        intent="knowledge_lookup",
        lookup_target="policies",
        policy_queries=["return window eligibility for electronics"],
    )

    assert analyze_query_module.build_policy_queries("what's the return window?", analysis) == [
        "what's the return window?",
        "return window eligibility for electronics",
    ]


async def test_lookup_target_is_written_to_state(monkeypatch) -> None:
    async def fake_core(query: str) -> QueryAnalysis:
        return QueryAnalysis(intent="knowledge_lookup", lookup_target="cases")

    monkeypatch.setattr(analyze_query_module, "analyze_query_core", fake_core)

    update = await analyze_query_module.analyze_query({"query": "cases where a refund was issued"})

    assert update["intent"] == "knowledge_lookup"
    assert update["lookup_target"] == "cases"


async def test_risk_flags_on_a_lookup_are_dropped(monkeypatch) -> None:
    """A lookup has no reply for a lead to review, whatever the model flagged."""

    async def fake_core(query: str) -> QueryAnalysis:
        return QueryAnalysis(intent="knowledge_lookup", risk_flags=["legal", "safety"])

    monkeypatch.setattr(analyze_query_module, "analyze_query_core", fake_core)

    update = await analyze_query_module.analyze_query({"query": "policy on injury claims?"})

    assert update["risk_flags"] == []
    assert update["requires_lead_review"] is False


HISTORY = [
    HumanMessage("X200 vacuum stopped charging after 3 months, 12-month warranty"),
    AIMessage("Covered as a defect [1]."),
]
FOLLOW_UP = "what if it's past 12 months?"


def _install_model_stub(monkeypatch, reply: TurnAnalysis | QueryAnalysis | Exception) -> list[str]:
    """Replace only the chat model, so the real prompt template still renders."""
    prompts: list[str] = []

    def fake_model(prompt_value):
        prompts.append(prompt_value.to_string())
        if isinstance(reply, Exception):
            raise reply
        return reply

    class _FakeChat:
        def with_structured_output(self, schema):
            return RunnableLambda(fake_model)

    monkeypatch.setattr(analyze_query_module, "get_chat_model", lambda model: _FakeChat())
    return prompts


async def test_a_first_turn_is_analyzed_as_typed(monkeypatch) -> None:
    prompts = _install_model_stub(monkeypatch, _canned_analysis())

    update = await analyze_query_module.analyze_query({"query": "my X200 died"})

    assert update["query"] == "my X200 died"
    assert update["user_message"] == "my X200 died"
    assert "<conversation>" not in prompts[0].split("<input>")[-1]
    assert len(prompts) == 1


async def test_a_follow_up_is_rewritten_in_the_same_call(monkeypatch) -> None:
    standalone = "The customer's X200 stopped charging. What if it is past 12 months?"
    prompts = _install_model_stub(
        monkeypatch, TurnAnalysis(standalone_query=f" {standalone}\n", analysis=_canned_analysis())
    )

    update = await analyze_query_module.analyze_query(
        {"query": FOLLOW_UP, "chat_history": HISTORY}
    )

    assert len(prompts) == 1
    assert "Agent: X200 vacuum stopped charging" in prompts[0]
    assert f"<input>\n{FOLLOW_UP}\n</input>" in prompts[0]
    assert update["query"] == standalone
    assert update["user_message"] == FOLLOW_UP
    assert update["policy_queries"][0] == standalone


async def test_an_empty_rewrite_keeps_the_message_as_typed(monkeypatch) -> None:
    _install_model_stub(monkeypatch, TurnAnalysis(analysis=_canned_analysis()))

    update = await analyze_query_module.analyze_query(
        {"query": "New customer: kettle lid snapped", "chat_history": HISTORY}
    )

    assert update["query"] == "New customer: kettle lid snapped"


async def test_a_failed_follow_up_call_falls_back_to_the_typed_message(monkeypatch) -> None:
    async def failing_turn_core(query: str, conversation: str):
        raise RuntimeError("bad structured output")

    async def fake_core(query: str) -> QueryAnalysis:
        return _canned_analysis()

    monkeypatch.setattr(analyze_query_module, "analyze_turn_core", failing_turn_core)
    monkeypatch.setattr(analyze_query_module, "analyze_query_core", fake_core)

    update = await analyze_query_module.analyze_query(
        {"query": FOLLOW_UP, "chat_history": HISTORY}
    )

    assert update["query"] == FOLLOW_UP
    assert update["intent"] == "complaint_query"
