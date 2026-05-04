"""Aggregate scores for one generation leg — the summary a plain `pytest` run omits.

The generation counterpart to `retriever/aggregate.py`, and deliberately the same
shape: same arguments, same results layout, same reasons for the bootstrap below.

    uv run python evals/generator/aggregate.py --leg policy-graph-generate

Unlike the retriever legs, every golden here runs a generation call as well as the
retrieval fan-out, so a run costs materially more. Qdrant must be up and the
policies collection populated first — see the README.
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
for _stream in (sys.stdout, sys.stderr):
    # stderr as well as stdout: `basicConfig` puts its handler on stderr, and the
    # goldens are full of em-dashes and ₹, which a cp1252 console mangles.
    if hasattr(_stream, "reconfigure"):
        _stream.reconfigure(encoding="utf-8", errors="replace")
setup_logging()
os.environ.setdefault("DEEPEVAL_TELEMETRY_OPT_OUT", "YES")
os.environ.setdefault("DEEPEVAL_RETRY_MAX_ATTEMPTS", "4")
os.environ.setdefault("DEEPEVAL_RETRY_INITIAL_SECONDS", "2")
os.environ.setdefault("DEEPEVAL_RETRY_CAP_SECONDS", "10")

from adapters import build_cases, graph_generation_case
from deepeval import evaluate
from deepeval.dataset import EvaluationDataset
from deepeval.evaluate import AsyncConfig, DisplayConfig, ErrorConfig
from deepeval.test_case import LLMTestCase
from metrics import GENERATION_METRICS, JUDGE_MODEL

from cms.config.settings import get_settings
from cms.rag.context import MARKER_PATTERN
from cms.retrieval.retrievers.policy_retriever import DEFAULT_TOP_N as POLICY_TOP_N

DATASETS = Path(__file__).parents[1] / "datasets"
# Absolute, so the run lands in the same place whatever the working directory is,
# and timestamped per run so legs stay comparable after the fact.
DEFAULT_RESULTS_FOLDER = Path(__file__).parents[1] / "results"

# The prompt `generate_core` loads. Recorded as a hyperparameter because it is
# half of what determines a score — a v2 prompt is a different system under test.
PROMPT_VERSION = "generate/v1"

# leg -> (dataset file, the coroutine that runs it).
LEGS = {
    "policy-graph-generate": ("policies.json", graph_generation_case),
}
DEFAULT_LEG = "policy-graph-generate"

# Half of deepeval's default of 20: that many simultaneous TLS handshakes through
# the local intercepting proxy is where connection errors start.
DEFAULT_MAX_CONCURRENT = 10


def log_citation_health(cases: list[tuple[list[str], str]]) -> None:
    """Two counts no judge is needed for, so they are free once generation has run.

    A draft citing nothing is ungrounded prose. A draft citing a marker that was
    never offered is a fabricated reference. `used_citations` warns about both
    per-draft; this is the per-run total.
    """
    ungrounded = 0
    fabricated = 0

    for contexts, draft in cases:
        markers = {int(marker) for marker in MARKER_PATTERN.findall(draft)}
        if not markers:
            ungrounded += 1
        elif any(marker < 1 or marker > len(contexts) for marker in markers):
            fabricated += 1

    print(
        f"\ncitation health: {len(cases)} draft(s), "
        f"{ungrounded} citing nothing, {fabricated} citing a marker never offered"
    )


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Score one generation leg and print deepeval's aggregate metrics."
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
    dataset_file, run_case = LEGS[args.leg]

    dataset = EvaluationDataset()
    dataset.add_goldens_from_json_file(file_path=str(DATASETS / dataset_file))

    # Retrieval and generation both run here, before evaluate() takes over the
    # event loop — build_cases calls asyncio.run(), which refuses to nest.
    cases = build_cases(run_case, [golden.input for golden in dataset.goldens])
    log_citation_health(cases)

    test_cases = [
        LLMTestCase(
            input=golden.input,
            actual_output=draft,
            expected_output=golden.expected_output,
            retrieval_context=contexts,
        )
        for golden, (contexts, draft) in zip(dataset.goldens, cases, strict=True)
    ]

    evaluate(
        test_cases=test_cases,
        metrics=GENERATION_METRICS,
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
            "top_n": POLICY_TOP_N,
            # The two that make a generation run attributable: change either and
            # the scores describe a different system.
            "generation_model": get_settings().openrouter_model_main,
            "prompt_version": PROMPT_VERSION,
            "judge_model": JUDGE_MODEL,
            "golden_set": dataset_file,
        },
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
