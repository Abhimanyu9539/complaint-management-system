"""Aggregate scores for one retrieval leg — the summary a plain `pytest` run omits.

`deepeval test run` builds its table in the CLI process after pytest returns, so
running the test files under pytest directly prints per-golden results and nothing
else. `evaluate()` wraps up its own run, so it prints the Aggregate Metrics table
(average score and pass rate per metric) plus the cost line.

Same goldens, same adapters, same judge as the six test files.

    uv run python evals/retriever/aggregate.py --leg policy-hybrid
    uv run python evals/retriever/aggregate.py --leg policy-dense
    uv run python evals/retriever/aggregate.py --leg policy-hybrid-rerank
    uv run python evals/retriever/aggregate.py --leg case-dense

Qdrant must be up and the collection populated first — see the README.
"""

import argparse
import os
import sys
from pathlib import Path

import cms.config  # noqa: F401 — truststore injection; must precede any HTTPS client
from cms.config.logging_config import setup_logging

# conftest.py does this for pytest runs; a standalone script has to do it itself,
# and before metrics.py is imported — that module builds the judge at import time.
# Hence the deferred imports below.
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
setup_logging()
os.environ.setdefault("DEEPEVAL_TELEMETRY_OPT_OUT", "YES")
os.environ.setdefault("DEEPEVAL_RETRY_MAX_ATTEMPTS", "4")
os.environ.setdefault("DEEPEVAL_RETRY_INITIAL_SECONDS", "2")
os.environ.setdefault("DEEPEVAL_RETRY_CAP_SECONDS", "10")

from adapters import (
    CASE_K,
    POLICY_K,
    POLICY_TOP_N,
    dense_case_context,
    dense_policy_context,
    hybrid_case_context,
    hybrid_policy_context,
    reranked_dense_policy_context,
    reranked_hybrid_policy_context,
    sparse_case_context,
    sparse_policy_context,
)
from deepeval import evaluate
from deepeval.dataset import EvaluationDataset
from deepeval.evaluate import AsyncConfig, DisplayConfig, ErrorConfig
from deepeval.test_case import LLMTestCase
from metrics import JUDGE_MODEL, RETRIEVER_METRICS

DATASETS = Path(__file__).parents[1] / "datasets"
# Absolute, so the run lands in the same place whatever the working directory is.
# `.deepeval/.latest_test_run.json` is a fixed path every run overwrites; this
# folder gets a timestamped `test_run_<YYYYMMDD_HHMMSS>.json` per run instead, so
# legs are still there to compare afterwards — and parallel legs don't collide.
DEFAULT_RESULTS_FOLDER = Path(__file__).parents[1] / "results"

# leg -> (dataset file, context adapter, the k that adapter retrieves at, top_n).
# `top_n` is None for the legs that return the raw pool; on the `-rerank` legs it
# is what survives, and the pair is what makes the precision comparison readable.
LEGS = {
    "policy-dense": ("policies.json", dense_policy_context, POLICY_K, None),
    "policy-sparse": ("policies.json", sparse_policy_context, POLICY_K, None),
    "policy-hybrid": ("policies.json", hybrid_policy_context, POLICY_K, None),
    "policy-dense-rerank": (
        "policies.json",
        reranked_dense_policy_context,
        POLICY_K,
        POLICY_TOP_N,
    ),
    "policy-hybrid-rerank": (
        "policies.json",
        reranked_hybrid_policy_context,
        POLICY_K,
        POLICY_TOP_N,
    ),
    "case-dense": ("cases.json", dense_case_context, CASE_K, None),
    "case-sparse": ("cases.json", sparse_case_context, CASE_K, None),
    "case-hybrid": ("cases.json", hybrid_case_context, CASE_K, None),
}
DEFAULT_LEG = "policy-hybrid"
# Half of deepeval's default of 20: that many simultaneous TLS handshakes through
# the local intercepting proxy is where connection errors start. Lower it further
# when running several legs at once — they share one judge account, and the rate
# limit is per account, not per process.
DEFAULT_MAX_CONCURRENT = 10


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Score one retrieval leg and print deepeval's aggregate metrics."
    )
    parser.add_argument(
        "--leg",
        choices=list(LEGS),
        default=DEFAULT_LEG,
        help=f"Which leg to score. Default: {DEFAULT_LEG}.",
    )
    parser.add_argument(
        "--max-concurrent",
        type=int,
        default=DEFAULT_MAX_CONCURRENT,
        help=f"Judge calls in flight at once (default: {DEFAULT_MAX_CONCURRENT}).",
    )
    parser.add_argument(
        "--ignore-errors",
        action="store_true",
        help=(
            "Finish the run when a judge call fails instead of aborting. The "
            "aggregate then covers only the cases that scored, so treat the "
            "numbers as partial."
        ),
    )
    parser.add_argument(
        "--results-folder",
        default=str(DEFAULT_RESULTS_FOLDER),
        help="Where to write the timestamped run JSON. Default: evals/results/.",
    )
    args = parser.parse_args()
    dataset_file, retrieve_context, k, top_n = LEGS[args.leg]

    dataset = EvaluationDataset()
    dataset.add_goldens_from_json_file(file_path=str(DATASETS / dataset_file))

    # Retrieval runs here, before evaluate() takes over the event loop — the
    # adapters call asyncio.run(), which refuses to nest inside a running one.
    # `actual_output` stays unset: neither metric needs it, and nothing generated
    # an answer. `golden.context` is never passed — only what the retriever found.
    test_cases = [
        LLMTestCase(
            input=golden.input,
            expected_output=golden.expected_output,
            retrieval_context=retrieve_context(golden.input),
        )
        for golden in dataset.goldens
    ]

    evaluate(
        test_cases=test_cases,
        metrics=RETRIEVER_METRICS,
        identifier=args.leg,
        async_config=AsyncConfig(max_concurrent=args.max_concurrent),
        error_config=ErrorConfig(ignore_errors=args.ignore_errors),
        display_config=DisplayConfig(
            results_folder=args.results_folder,
            # One subfolder per leg, so a leg's runs sit together over time.
            results_subfolder=args.leg,
        ),
        hyperparameters={
            "leg": args.leg,
            "top_k": k,
            # The results folder now holds two shapes of policy run; these say
            # which configuration produced a given file.
            "rerank": top_n is not None,
            "top_n": top_n,
            "judge_model": JUDGE_MODEL,
            "golden_set": dataset_file,
        },
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
