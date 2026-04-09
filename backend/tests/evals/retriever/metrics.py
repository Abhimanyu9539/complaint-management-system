"""The three retriever metrics, shared by all three eval files.

Kept in one module so dense, sparse and hybrid are scored by identical judges
at identical thresholds — otherwise the three runs are not comparable, which is
the whole point of running them separately.
"""

import logging

from deepeval.metrics import (
    ContextualPrecisionMetric,
    ContextualRecallMetric,
    ContextualRelevancyMetric,
)
from deepeval.models import OpenAIModel

logger = logging.getLogger(__name__)

# deepeval knows this model (models/llms/constants.py), which matters in three
# ways: it forces temperature=1 rather than the 0.0 the gpt-5 reasoning
# endpoint rejects, it uses native structured outputs for the verdicts, and its
# prices are registered so --cost-tracking reports a real number.
JUDGE_MODEL = "gpt-5.4-mini"

try:
    _judge = OpenAIModel(model=JUDGE_MODEL)
except Exception:
    logger.exception("Could not build the %s judge", JUDGE_MODEL)
    raise

# Relevancy sits lower on purpose: it penalises every irrelevant *sentence*
# inside an otherwise-correct chunk, and policies are chunked at 800 tokens.
RETRIEVER_METRICS = [
    ContextualPrecisionMetric(threshold=0.7, model=_judge, include_reason=True),
    ContextualRecallMetric(threshold=0.7, model=_judge, include_reason=True),
    ContextualRelevancyMetric(threshold=0.5, model=_judge, include_reason=True),
]
