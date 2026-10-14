from unittest.mock import AsyncMock

import pytest

from cms.services import admin_stats


def _step(node: str, ms: int, started_at: str = "2026-10-03T10:00:00+00:00") -> dict:
    return {"node": node, "started_at": started_at, "ms": ms, "ok": True}


RUNS = [
    {
        "status": "succeeded",
        "outcome": "drafted",
        "latency_ms": 1000,
        "steps": [_step("classify_ticket", 300), _step("draft_reply", 600)],
    },
    {
        "status": "succeeded",
        "outcome": "needs_review",
        "latency_ms": 3000,
        "steps": [_step("classify_ticket", 500), _step("draft_reply", 2000), _step("draft_reply", 400)],
    },
    {"status": "no_match", "outcome": "needs_review", "latency_ms": 2000, "steps": []},
    {"status": "failed", "outcome": "processing_failed", "latency_ms": None, "steps": []},
]


async def test_summary_counts_runs_and_latency(monkeypatch) -> None:
    monkeypatch.setattr(admin_stats.agent_runs, "list_runs_since", AsyncMock(return_value=RUNS))

    summary = await admin_stats.build_agent_summary(7)

    assert summary.range_days == 7 and summary.total == 4
    assert summary.by_status == {"succeeded": 2, "no_match": 1, "blocked": 0, "failed": 1}
    assert summary.by_outcome == {"drafted": 1, "needs_review": 2, "processing_failed": 1}
    assert summary.needs_review_rate == 0.5
    # A run with no latency is left out of the percentiles, not counted as 0.
    assert summary.latency.samples == 3
    assert summary.latency.p50_ms == 2000 and summary.latency.max_ms == 3000


async def test_node_latency_is_the_median_per_node_slowest_first(monkeypatch) -> None:
    monkeypatch.setattr(admin_stats.agent_runs, "list_runs_since", AsyncMock(return_value=RUNS))

    summary = await admin_stats.build_agent_summary(7)

    assert [(n.node, n.p50_ms, n.samples) for n in summary.node_latency] == [
        ("draft_reply", 600, 3),
        ("classify_ticket", 500, 2),
    ]


async def test_an_idle_window_has_no_rate_rather_than_zero(monkeypatch) -> None:
    monkeypatch.setattr(admin_stats.agent_runs, "list_runs_since", AsyncMock(return_value=[]))

    summary = await admin_stats.build_agent_summary(7)

    assert summary.total == 0
    assert summary.needs_review_rate is None
    assert summary.latency.p50_ms is None and summary.node_latency == []


async def test_run_page_sorts_steps_by_start_time(monkeypatch) -> None:
    row = {
        "id": "r1",
        "ticket_id": "t1",
        "ticket_no": 1042,
        "subject": "X200 won't charge",
        "trigger": "created",
        "status": "succeeded",
        "outcome": "drafted",
        "review_reasons": [],
        "regenerated": False,
        "precedents_offered": 0,
        "steps": [
            _step("analyze_ticket", 20, "2026-10-03T10:00:01+00:00"),
            _step("input_guard", 10, "2026-10-03T10:00:00+00:00"),
        ],
        "errors": {},
        "latency_ms": 900,
        "started_at": "2026-10-03T10:00:00+00:00",
        "finished_at": "2026-10-03T10:00:02+00:00",
    }
    monkeypatch.setattr(admin_stats.agent_runs, "list_runs", AsyncMock(return_value=([row], 1)))

    page = await admin_stats.build_agent_run_page(status=None, search=None, limit=25, offset=0)

    assert page.total == 1
    assert [step.node for step in page.items[0].steps] == ["input_guard", "analyze_ticket"]


def _call(model: str, cost: float | None, input_tokens: int = 100, output_tokens: int = 20) -> dict:
    return {
        "node": "draft_reply",
        "model": model,
        "input_tokens": input_tokens,
        "output_tokens": output_tokens,
        "total_tokens": input_tokens + output_tokens,
        "cost_usd": cost,
    }


async def test_summary_adds_up_cost_per_model_most_expensive_first(monkeypatch) -> None:
    rows = [
        {**RUNS[0], "cost_usd": 0.003, "llm_calls": [_call("cheap", 0.001), _call("main", 0.002)]},
        # A call with no reported cost counts its tokens but adds no cost.
        {**RUNS[1], "cost_usd": 0.004, "llm_calls": [_call("main", 0.004), _call("cheap", None)]},
        RUNS[2],
    ]
    monkeypatch.setattr(admin_stats.agent_runs, "list_runs_since", AsyncMock(return_value=rows))

    summary = await admin_stats.build_agent_summary(7)

    assert summary.cost_usd == pytest.approx(0.007)
    assert [(m.model, m.calls, m.input_tokens, m.output_tokens) for m in summary.cost_by_model] == [
        ("main", 2, 200, 40),
        ("cheap", 2, 200, 40),
    ]
    assert summary.cost_by_model[0].cost_usd == pytest.approx(0.006)


async def test_run_page_maps_the_llm_calls(monkeypatch) -> None:
    row = {
        "id": "r1",
        "ticket_id": "t1",
        "trigger": "created",
        "status": "succeeded",
        "regenerated": False,
        "precedents_offered": 0,
        "llm_calls": [_call("main", 0.002), _call("nemo", None)],
        "input_tokens": 200,
        "output_tokens": 40,
        "cost_usd": "0.002000",
        "started_at": "2026-10-03T10:00:00+00:00",
        "finished_at": "2026-10-03T10:00:02+00:00",
    }
    monkeypatch.setattr(admin_stats.agent_runs, "list_runs", AsyncMock(return_value=([row], 1)))

    page = await admin_stats.build_agent_run_page(status=None, search=None, limit=25, offset=0)

    [run] = page.items
    assert [(call.model, call.cost_usd) for call in run.llm_calls] == [("main", 0.002), ("nemo", None)]
    assert run.input_tokens == 200 and run.output_tokens == 40 and run.cost_usd == 0.002
