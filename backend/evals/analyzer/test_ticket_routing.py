"""Ticket routing: does `classify_ticket_core` put each golden complaint with a department that owns it?

Real calls on the cheap model, one per golden — no metrics, plain counts.
Run with `uv run pytest evals/analyzer/test_ticket_routing.py -s` to see the table.
"""

import asyncio
import json
from pathlib import Path
from statistics import mean

import pytest

from cms.config.settings import get_settings
from cms.rag.nodes.classify_ticket import classify_ticket_core
from cms.schemas.ticket_classification import TicketClassification

DATASETS = Path(__file__).parents[1] / "datasets"
GOLDENS = json.loads((DATASETS / "tickets.json").read_text(encoding="utf-8"))

# Top-1 accuracy the classifier must keep. Baseline 26/30 (0.87, 2026-10-03), less two goldens for variance.
ROUTING_ACCURACY_FLOOR = 0.80


def expected_departments(golden: dict) -> list[str]:
    return golden["additional_metadata"]["expected_departments"]


async def _classify_all(complaints: list[str]) -> list[TicketClassification]:
    # One at a time, like test_intent_routing: OpenRouter reserves credit per in-flight request.
    return [await classify_ticket_core(complaint) for complaint in complaints]


@pytest.fixture(scope="module")
def classifications() -> list[TicketClassification]:
    """Every golden classified once, on one event loop — the cached chat client binds to it."""
    return asyncio.run(_classify_all([golden["input"] for golden in GOLDENS]))


def _mean(values: list[float]) -> str:
    return f"{mean(values):.2f}" if values else "—"


def test_routing_accuracy(classifications: list[TicketClassification]) -> None:
    floor = get_settings().routing_confidence_floor
    top1 = top2 = below_floor = 0
    right_confidence: list[float] = []
    wrong_confidence: list[float] = []

    print(f"\n{'#':>2}  {'expected':<28} {'predicted':<15} {'conf':>4}")
    for index, (golden, result) in enumerate(zip(GOLDENS, classifications, strict=True)):
        expected = expected_departments(golden)
        hit = result.department in expected
        top1 += hit
        top2 += any(candidate.department in expected for candidate in result.candidates[:2])
        below_floor += result.confidence < floor
        (right_confidence if hit else wrong_confidence).append(result.confidence)
        print(
            f"{index:>2}  {'/'.join(expected):<28} {result.department:<15} "
            f"{result.confidence:.2f}  {'✓' if hit else '✗'}"
        )

    total = len(GOLDENS)
    print(
        f"\ntop-1 {top1}/{total} ({top1 / total:.0%}), top-2 {top2}/{total} ({top2 / total:.0%})\n"
        f"mean confidence: {_mean(right_confidence)} when right, {_mean(wrong_confidence)} when wrong\n"
        f"below the {floor:.2f} routing floor: {below_floor}/{total}"
    )
    assert top1 / total >= ROUTING_ACCURACY_FLOOR
