"""Prometheus metrics, served at `/metrics`. Every `record_*` helper swallows its own failure."""

import logging

from prometheus_client import Counter, Histogram

from cms.config.settings import get_settings

logger = logging.getLogger(__name__)

# Guard outcomes, for the `result` label.
GUARD_PASSED = "passed"
GUARD_BLOCKED = "blocked"
GUARD_ERROR = "error"

TICKET_TRANSITIONS = Counter(
    "cms_ticket_transitions_total",
    "Tickets entering each status: the status funnel.",
    ["status"],
)
GRAPH_DURATION = Histogram(
    "cms_ticket_graph_duration_seconds",
    "Ticket-graph run time, by how the run ended.",
    ["status"],
    buckets=get_settings().graph_latency_buckets,
)
GUARD_CHECKS = Counter(
    "cms_guard_checks_total",
    "Guard checks, by guard node and result (passed, blocked, error).",
    ["guard", "result"],
)
LLM_TOKENS = Counter(
    "cms_llm_tokens_total",
    "LLM tokens, by model, node and type (input, output).",
    ["model", "node", "type"],
)
LLM_COST = Counter(
    "cms_llm_cost_usd_total",
    "LLM cost in USD as OpenRouter billed it, by model and node.",
    ["model", "node"],
)
FLYWHEEL_OUTCOMES = Counter(
    "cms_flywheel_outcomes_total",
    "Tickets the daily minting job handled, by outcome (minted, duplicate, skipped, failed).",
    ["outcome"],
)


def record_transition(status: str) -> None:
    try:
        TICKET_TRANSITIONS.labels(status).inc()
    except Exception:
        logger.exception("Could not count the move to %s", status)


def record_graph_run(status: str, latency_ms: int) -> None:
    try:
        GRAPH_DURATION.labels(status).observe(latency_ms / 1000)
    except Exception:
        logger.exception("Could not record the graph run's latency")


def record_guard(guard: str, result: str) -> None:
    try:
        GUARD_CHECKS.labels(guard, result).inc()
    except Exception:
        logger.exception("Could not count the %s check", guard)


def record_flywheel_outcome(outcome: str) -> None:
    try:
        FLYWHEEL_OUTCOMES.labels(outcome).inc()
    except Exception:
        logger.exception("Could not count the flywheel outcome %s", outcome)


def record_llm_call(call: dict) -> None:
    try:
        model, node = call["model"], call["node"]
        LLM_TOKENS.labels(model, node, "input").inc(call["input_tokens"])
        LLM_TOKENS.labels(model, node, "output").inc(call["output_tokens"])
        if call["cost_usd"] is not None:
            LLM_COST.labels(model, node).inc(call["cost_usd"])
    except Exception:
        logger.exception("Could not count an LLM call")
