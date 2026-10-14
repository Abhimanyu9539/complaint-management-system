from uuid import uuid4

import pytest
from langchain_core.messages import AIMessage
from langchain_core.outputs import ChatGeneration, LLMResult
from prometheus_client import REGISTRY

from cms.observability.usage import UsageCollector


async def _report(collector: UsageCollector, metadata: dict, cost: float | None = 0.002) -> None:
    """One chat-model call, as LangChain reports it to a callback handler."""
    run_id = uuid4()
    await collector.on_chat_model_start({}, [], run_id=run_id, metadata=metadata)
    message = AIMessage(
        content="ok",
        usage_metadata={"input_tokens": 100, "output_tokens": 20, "total_tokens": 120},
        response_metadata={"cost": cost} if cost is not None else {},
    )
    await collector.on_llm_end(LLMResult(generations=[[ChatGeneration(message=message)]]), run_id=run_id)


def _sample(name: str, labels: dict) -> float:
    return REGISTRY.get_sample_value(name, labels) or 0.0


async def test_each_call_is_recorded_with_its_node_model_tokens_and_cost() -> None:
    collector = UsageCollector(default_node="ticket_graph")

    await _report(collector, {"langgraph_node": "draft_reply", "ls_model_name": "test/main"})

    assert collector.calls == [
        {
            "node": "draft_reply",
            "model": "test/main",
            "input_tokens": 100,
            "output_tokens": 20,
            "total_tokens": 120,
            "cost_usd": 0.002,
        }
    ]


async def test_a_call_outside_the_graph_takes_the_default_node() -> None:
    collector = UsageCollector(default_node="dept_question")

    await _report(collector, {"ls_model_name": "test/cheap"})

    assert collector.calls[0]["node"] == "dept_question"


async def test_totals_skip_a_missing_cost() -> None:
    collector = UsageCollector(default_node="ticket_graph")

    await _report(collector, {"ls_model_name": "test/main"}, cost=0.002)
    await _report(collector, {"ls_model_name": "test/nemo"}, cost=None)

    assert collector.calls[1]["cost_usd"] is None
    assert collector.totals() == {"input_tokens": 200, "output_tokens": 40, "cost_usd": 0.002}


async def test_calls_are_counted_in_the_metrics() -> None:
    labels = {"model": "test/metrics", "node": "classify_ticket"}
    tokens_before = _sample("cms_llm_tokens_total", {**labels, "type": "input"})
    cost_before = _sample("cms_llm_cost_usd_total", labels)
    collector = UsageCollector(default_node="ticket_graph")

    await _report(collector, {"langgraph_node": "classify_ticket", "ls_model_name": "test/metrics"})

    assert _sample("cms_llm_tokens_total", {**labels, "type": "input"}) - tokens_before == 100
    assert _sample("cms_llm_cost_usd_total", labels) - cost_before == pytest.approx(0.002)


async def test_an_unreadable_response_is_skipped_not_raised() -> None:
    collector = UsageCollector(default_node="ticket_graph")

    await collector.on_llm_end(LLMResult(generations=[]), run_id=uuid4())

    assert collector.calls == []
