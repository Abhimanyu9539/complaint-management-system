"""The three retriever metrics, shared so all three legs are scored identically.

Same judge, same thresholds, and adapters.py feeds them the same k — otherwise the
dense/sparse/hybrid comparison, which is the point of the suite, means nothing.
"""

import logging

from deepeval.metrics import (
    ContextualPrecisionMetric,
    ContextualRecallMetric,
    ContextualRelevancyMetric,  # noqa: F401 — parked; see RETRIEVER_METRICS below
)
from deepeval.models import OpenAIModel

from cms.config.settings import get_settings

logger = logging.getLogger(__name__)

JUDGE_MODEL = "gpt-5.4-mini"

PRECISION_THRESHOLD = 0.7
RECALL_THRESHOLD = 0.7
# Relevancy sits lower on purpose: it penalises every irrelevant *sentence* inside
# an otherwise-correct chunk, and chunk_policy cuts policies at 800 tokens. A 0.7
# bar here would fail retrievals that are in fact correct.
RELEVANCY_THRESHOLD = 0.5

try:
    _settings = get_settings()
    _judge = OpenAIModel(
        model=JUDGE_MODEL,
        api_key=_settings.open_router_api_key,
        base_url=_settings.openrouter_base_url,
    )
except Exception:
    logger.exception("Could not build the %s judge", JUDGE_MODEL)
    raise

RETRIEVER_METRICS = [
    ContextualPrecisionMetric(threshold=PRECISION_THRESHOLD, model=_judge, include_reason=True),
    ContextualRecallMetric(threshold=RECALL_THRESHOLD, model=_judge, include_reason=True),
    #ContextualRelevancyMetric(threshold=RELEVANCY_THRESHOLD, model=_judge, include_reason=True),
]
