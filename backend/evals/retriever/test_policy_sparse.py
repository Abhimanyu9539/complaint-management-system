"""ContextualPrecision / Recall / Relevancy for the sparse (lexical) policy leg.

BM25 via local fastembed — matches exact terms, and nothing costs an API call.

Run separately from its siblings and compare the means — that comparison is why
these are three files and not one. Driven by the raw `golden.input`: no query
rewriting, no department filter, so the scores describe retrieval and nothing
upstream of it.
"""

from pathlib import Path

import pytest
from adapters import sparse_policy_context
from deepeval import assert_test
from deepeval.dataset import EvaluationDataset, Golden
from deepeval.test_case import LLMTestCase
from metrics import RETRIEVER_METRICS

dataset = EvaluationDataset()
dataset.add_goldens_from_json_file(
    file_path=str(Path(__file__).parents[1] / "datasets" / "policies.json")
)


@pytest.mark.parametrize("golden", dataset.goldens)
def test_sparse_policy_retriever(golden: Golden) -> None:
    # `actual_output` stays unset: nothing generated an answer, and none of these
    # three metrics require it. `golden.context` is never passed either — only
    # what the retriever actually found.
    test_case = LLMTestCase(
        input=golden.input,
        expected_output=golden.expected_output,
        retrieval_context=sparse_policy_context(golden.input),
    )
    assert_test(test_case=test_case, metrics=RETRIEVER_METRICS)
