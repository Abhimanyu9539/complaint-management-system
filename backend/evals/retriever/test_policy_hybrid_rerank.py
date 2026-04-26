"""ContextualPrecision / Recall for the reranked hybrid policy leg.

The same hybrid candidates as `test_policy_hybrid.py`, Voyage-reranked down to
`POLICY_TOP_N`. Run it against that file and compare the means: the wide pool is
there for recall, and this is the leg that has to earn the precision back.
"""

from pathlib import Path

import pytest
from adapters import reranked_hybrid_policy_context
from deepeval import assert_test
from deepeval.dataset import EvaluationDataset, Golden
from deepeval.test_case import LLMTestCase
from metrics import RETRIEVER_METRICS

dataset = EvaluationDataset()
dataset.add_goldens_from_json_file(
    file_path=str(Path(__file__).parents[1] / "datasets" / "policies.json")
)


@pytest.mark.parametrize("golden", dataset.goldens)
def test_reranked_hybrid_policy_retriever(golden: Golden) -> None:
    # Same judge, same thresholds, same goldens as the unreranked leg — the
    # reranker is the only thing that differs, which is the point.
    test_case = LLMTestCase(
        input=golden.input,
        expected_output=golden.expected_output,
        retrieval_context=reranked_hybrid_policy_context(golden.input),
    )
    assert_test(test_case=test_case, metrics=RETRIEVER_METRICS)
