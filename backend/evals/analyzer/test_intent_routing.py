"""Intent routing: complaint goldens stay complaints, agent lookups reach the lookup branch.

Real calls to `analyze_query_core` on the cheap model — no metrics, plain asserts.
Run with `uv run pytest evals/analyzer -v`.
"""

import asyncio
import json
from pathlib import Path

import pytest

from cms.rag.nodes.analyze_query import analyze_query_core
from cms.schemas.query_analysis import QueryAnalysis

DATASETS = Path(__file__).parents[1] / "datasets"
COMPLAINTS = [
    golden["input"]
    for golden in json.loads((DATASETS / "policies.json").read_text(encoding="utf-8"))
]
LOOKUPS = json.loads((DATASETS / "lookups.json").read_text(encoding="utf-8"))


async def _classify_all(queries: list[str]) -> list[QueryAnalysis]:
    # One at a time: OpenRouter reserves credit per in-flight request, and 42 at once
    # can be refused on a small balance.
    return [await analyze_query_core(query) for query in queries]


@pytest.fixture(scope="module")
def analyses() -> dict[str, QueryAnalysis]:
    """Every query classified once, on one event loop — the cached chat client binds to it."""
    queries = COMPLAINTS + [item["input"] for item in LOOKUPS]
    return dict(zip(queries, asyncio.run(_classify_all(queries))))


@pytest.mark.parametrize("query", COMPLAINTS, ids=[f"complaint-{i}" for i in range(len(COMPLAINTS))])
def test_complaint_stays_a_complaint(analyses: dict[str, QueryAnalysis], query: str) -> None:
    assert analyses[query].intent == "complaint_query"


@pytest.mark.parametrize("item", LOOKUPS, ids=[item["input"][:50] for item in LOOKUPS])
def test_lookup_is_routed_with_its_target(analyses: dict[str, QueryAnalysis], item: dict) -> None:
    analysis = analyses[item["input"]]

    assert analysis.intent == "knowledge_lookup"
    assert analysis.lookup_target == item["lookup_target"]
