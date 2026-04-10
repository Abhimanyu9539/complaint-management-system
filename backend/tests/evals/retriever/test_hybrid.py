"""ContextualPrecision / Recall / Relevancy for the production retriever: both legs, both collections, RRF-fused.

Run separately from its dense/sparse/hybrid siblings and compare the means —
that comparison is the reason these are three files and not one.

The retriever is driven by the raw `golden.input`: no query rewriting, no
department filter, so the scores describe retrieval and nothing upstream of it.
"""

from pathlib import Path

import pytest
from adapters import hybrid_context
from deepeval import assert_test
from deepeval.dataset import EvaluationDataset, Golden
from deepeval.test_case import LLMTestCase
from metrics import RETRIEVER_METRICS

dataset = EvaluationDataset()
dataset.add_goldens_from_json_file(
    file_path=str(Path(__file__).parents[1] / "data" / ".dataset.json")
)


@pytest.mark.parametrize("golden", dataset.goldens)
def test_hybrid_retriever(golden: Golden):
    # `actual_output` stays unset: nothing generated an answer, and none of
    # these three metrics require it. `golden.context` (the synthesizer's
    # source chunks) is never passed either — only what the retriever found.
    test_case = LLMTestCase(
        input=golden.input,
        expected_output=golden.expected_output,
        retrieval_context=hybrid_context(golden.input),
    )
    assert_test(test_case=test_case, metrics=RETRIEVER_METRICS)
