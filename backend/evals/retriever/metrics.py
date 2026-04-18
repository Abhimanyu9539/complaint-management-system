"""The three retriever metrics, shared so all three legs are scored identically.

Same judge, same thresholds, and adapters.py feeds them the same k — otherwise the
dense/sparse/hybrid comparison, which is the point of the suite, means nothing.
"""

import logging

from deepeval.metrics import (
    ContextualPrecisionMetric,
    ContextualRecallMetric,
    ContextualRelevancyMetric,
)
from deepeval.models import OpenAIModel

logger = logging.getLogger(__name__)

# deepeval has this id in its model registry, which buys three things: it forces
# temperature=1 (the gpt-5 reasoning endpoint rejects 0.0), it uses native
# structured outputs for the verdicts, and its prices are registered so the cost
# line at the end of a run is a real number.
JUDGE_MODEL = "gpt-5.4-mini"

PRECISION_THRESHOLD = 0.7
RECALL_THRESHOLD = 0.7
# Relevancy sits lower on purpose: it penalises every irrelevant *sentence* inside
# an otherwise-correct chunk, and chunk_policy cuts policies at 800 tokens. A 0.7
# bar here would fail retrievals that are in fact correct.
RELEVANCY_THRESHOLD = 0.5

try:
    _judge = OpenAIModel(model=JUDGE_MODEL)
except Exception:
    logger.exception("Could not build the %s judge", JUDGE_MODEL)
    raise

RETRIEVER_METRICS = [
    ContextualPrecisionMetric(threshold=PRECISION_THRESHOLD, model=_judge, include_reason=True),
    ContextualRecallMetric(threshold=RECALL_THRESHOLD, model=_judge, include_reason=True),
    #ContextualRelevancyMetric(threshold=RELEVANCY_THRESHOLD, model=_judge, include_reason=True),
]
