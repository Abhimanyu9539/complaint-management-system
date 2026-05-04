"""The three generation metrics, shared so every generation leg is scored identically.

Same judge as `retriever/metrics.py`, constructed again rather than imported: the
suites live flat with no `__init__.py`, so sibling folders are not importable
across each other. Generation wants its own thresholds anyway.
"""

import logging

from deepeval.metrics import AnswerRelevancyMetric, FaithfulnessMetric, GEval
from deepeval.models import OpenAIModel
from deepeval.test_case import SingleTurnParams

from cms.config.settings import get_settings

logger = logging.getLogger(__name__)

# Unprefixed on purpose — see evals/README.md "The judge". deepeval looks the id
# up in its model registry with a plain dict lookup, and `openai/gpt-5.4-mini`
# would miss it and lose temperature=1, native structured outputs, and real prices.
JUDGE_MODEL = "gpt-5.4-mini"

# Faithfulness sits higher than the rest: an invented entitlement is the failure
# that actually costs something here, and it is the one a support agent is least
# able to catch. Relevancy and correctness match the retriever suite's 0.7.
FAITHFULNESS_THRESHOLD = 0.8
RELEVANCY_THRESHOLD = 0.7
CORRECTNESS_THRESHOLD = 0.7

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

# There is no generic "correctness" metric because correct depends on the task.
# Here it means: the draft reaches the policy conclusions the reference reaches.
# The last two steps matter as much as the first — the goldens are written in one
# particular order and wording, and a draft must not be marked down for choosing
# another.
CORRECTNESS = GEval(
    name="Correctness",
    threshold=CORRECTNESS_THRESHOLD,
    model=_judge,
    evaluation_steps=[
        (
            "Check whether 'actual output' reaches the same coverage decision as "
            "'expected output' — is the complaint covered, and under what conditions."
        ),
        (
            "Check whether it names the same remedy or entitlement (repair, replacement, "
            "refund, credit) and the same limits on it."
        ),
        (
            "Check whether it states the checks or verification the agent must confirm "
            "first, where 'expected output' states them."
        ),
        (
            "Penalise any coverage period, amount, deadline or entitlement that 'expected "
            "output' does not support. Penalise a promise the policy does not authorise."
        ),
        (
            "Do NOT penalise different wording, ordering, length or formatting. Do NOT "
            "penalise omitting a minor detail that does not change what the agent would do."
        ),
    ],
    evaluation_params=[
        SingleTurnParams.INPUT,
        SingleTurnParams.ACTUAL_OUTPUT,
        SingleTurnParams.EXPECTED_OUTPUT,
    ],
)

GENERATION_METRICS = [
    FaithfulnessMetric(
        threshold=FAITHFULNESS_THRESHOLD, model=_judge, include_reason=True
    ),
    AnswerRelevancyMetric(threshold=RELEVANCY_THRESHOLD, model=_judge, include_reason=True),
    CORRECTNESS,
]
