"""Collect each LLM call's tokens and cost, and count them in the metrics.

Passed in a run's `callbacks`; LangChain hands it to every chat model the run calls, NeMo's included.
"""

import logging
from typing import Any
from uuid import UUID

from langchain_core.callbacks import AsyncCallbackHandler
from langchain_core.outputs import LLMResult

from cms.observability import metrics

logger = logging.getLogger(__name__)

UNKNOWN_MODEL = "unknown"


class UsageCollector(AsyncCallbackHandler):
    """One `{node, model, input_tokens, output_tokens, total_tokens, cost_usd}` per call, in `calls`.

    `cost_usd` is what OpenRouter billed, or None when the client did not report it (NeMo's ChatOpenAI).
    """

    def __init__(self, default_node: str) -> None:
        self.default_node = default_node
        self.calls: list[dict] = []
        self._started: dict[UUID, tuple[str, str]] = {}

    async def on_chat_model_start(
        self,
        serialized: dict[str, Any],
        messages: list,
        *,
        run_id: UUID,
        metadata: dict[str, Any] | None = None,
        **kwargs: Any,
    ) -> None:
        metadata = metadata or {}
        self._started[run_id] = (
            metadata.get("langgraph_node") or self.default_node,
            metadata.get("ls_model_name") or UNKNOWN_MODEL,
        )

    async def on_llm_end(self, response: LLMResult, *, run_id: UUID, **kwargs: Any) -> None:
        node, model = self._started.pop(run_id, (self.default_node, UNKNOWN_MODEL))
        try:
            message = response.generations[0][0].message
            usage = message.usage_metadata or {}
            cost = message.response_metadata.get("cost")
            call = {
                "node": node,
                "model": model,
                "input_tokens": usage.get("input_tokens", 0),
                "output_tokens": usage.get("output_tokens", 0),
                "total_tokens": usage.get("total_tokens", 0),
                "cost_usd": float(cost) if cost is not None else None,
            }
        except Exception:
            logger.exception("Could not read the usage of an LLM call in %s", node)
            return
        self.calls.append(call)
        metrics.record_llm_call(call)

    async def on_llm_error(self, error: BaseException, *, run_id: UUID, **kwargs: Any) -> None:
        self._started.pop(run_id, None)

    def totals(self) -> dict:
        """The run's `input_tokens`, `output_tokens` and `cost_usd` (the sum of the costs reported)."""
        return {
            "input_tokens": sum(call["input_tokens"] for call in self.calls),
            "output_tokens": sum(call["output_tokens"] for call in self.calls),
            "cost_usd": round(sum(call["cost_usd"] or 0.0 for call in self.calls), 8),
        }
