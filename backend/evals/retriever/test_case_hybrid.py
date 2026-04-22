"""ContextualPrecision / Recall / Relevancy for the hybrid (production) case leg.

Both legs, fused server-side by Qdrant with RRF. This is what production uses.

Run separately from its siblings and compare the means — that comparison is why
these are three files and not one. Driven by the raw `golden.input`: no query
rewriting, no filter, so the scores describe retrieval and nothing upstream of it.
"""

from pathlib import Path

import pytest
from adapters import hybrid_case_context
from deepeval import assert_test
from deepeval.dataset import EvaluationDataset, Golden
from deepeval.test_case import LLMTestCase
from metrics import RETRIEVER_METRICS

dataset = EvaluationDataset()
dataset.add_goldens_from_json_file(
    file_path=str(Path(__file__).parents[1] / "datasets" / "cases.json")
)


@pytest.mark.parametrize("golden", dataset.goldens)
def test_hybrid_case_retriever(golden: Golden) -> None:
    # `actual_output` stays unset: nothing generated an answer, and none of these
    # three metrics require it. `golden.context` is never passed either — only
    # what the retriever actually found.
    test_case = LLMTestCase(
        input=golden.input,
        expected_output=golden.expected_output,
        retrieval_context=hybrid_case_context(golden.input),
    )
    assert_test(test_case=test_case, metrics=RETRIEVER_METRICS)
