"""CLI entrypoint for the standalone retrieval probe.

steps.md Step 5 calls for proving retrieval works "before any LLM touches it"
— this is that proof, repeatable from a terminal. The retrieval logic itself
lives in `cms.retrieval.retrievers`; this file only parses arguments, prints
results, and turns the outcome into an exit code.

Usage (from anywhere, once the project is installed):

    cms-retrieve "my ProBlend 300 shows ERR-22" --department tech_support
    cms-retrieve "ERR-22" --leg sparse                  # one leg in isolation
    cms-retrieve "warranty claim" --department warranty --department returns
"""

import argparse
import json
import logging
import sys

# The `cms.config` import must come first: importing it runs cms/config/__init__.py,
# which injects the OS trust store into ssl. That has to happen before any HTTPS
# client (openai, qdrant) is constructed.
from cms.config.logging_config import setup_logging
from cms.config.settings import get_settings
from cms.retrieval.retrievers.base import RetrievedChunk
from cms.retrieval.retrievers.dense_retriever import dense_search
from cms.retrieval.retrievers.hybrid_retriever import (
    DEFAULT_K_CASES,
    DEFAULT_K_POLICIES,
    build_filter,
    retrieve,
)
from cms.retrieval.retrievers.sparse_retriever import sparse_search

logger = logging.getLogger("cms.cli.retrieve")


def _print_group(label: str, chunks: list[RetrievedChunk]) -> None:
    print(f"\n--- {label} ({len(chunks)}) ---")
    if not chunks:
        print("  (no results)")
        return
    for rank, chunk in enumerate(chunks, start=1):
        snippet = " ".join(chunk.text.split())[:160]
        print(
            f"  {rank}. [{chunk.score:.4f}] {chunk.title or chunk.doc_id!r} "
            f"(doc_id={chunk.doc_id}, department={chunk.department})\n"
            f"      {snippet}"
        )


def _run_single_leg(args: argparse.Namespace) -> int:
    """`--leg dense` / `--leg sparse`: one corpus quota, one leg, no fusion.

    Exists so a leg can be inspected on its own — the whole reason the legs
    are separate modules rather than always composed through `retrieve()`.
    """
    settings = get_settings()
    search = dense_search if args.leg == "dense" else sparse_search

    cases = search(
        settings.qdrant_cases_collection,
        args.query,
        "case",
        args.k_cases,
        build_filter(args.department),
    )
    policies = search(
        settings.qdrant_policies_collection,
        args.query,
        "policy",
        args.k_policies,
        build_filter(args.department, published_only=not args.all_lifecycles),
    )

    if args.json:
        print(
            json.dumps(
                {
                    "leg": args.leg,
                    "cases": [c.model_dump() for c in cases],
                    "policies": [c.model_dump() for c in policies],
                },
                default=str,
            )
        )
        return 0

    print(f"leg={args.leg} query={args.query!r} departments={args.department}")
    _print_group("cases", cases)
    _print_group("policies", policies)
    return 0


def main() -> int:
    setup_logging()

    # Seed-corpus and future-uploaded text is arbitrary UTF-8 (currency signs,
    # accents, ...); Windows terminals default stdout to the system codepage
    # (cp1252), which cannot encode most of it. Reconfiguring avoids a crash
    # on retrieval hits this CLI has no control over the content of.
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")

    parser = argparse.ArgumentParser(
        description="Standalone hybrid retrieval probe over the seeded KB."
    )
    parser.add_argument("query", help="The question or complaint text to search for.")
    parser.add_argument(
        "--department",
        action="append",
        dest="department",
        help="Restrict to this department. Repeatable — several values widen the filter.",
    )
    parser.add_argument(
        "--leg",
        choices=("dense", "sparse", "hybrid"),
        default="hybrid",
        help="Run one leg in isolation, or the fused hybrid result (default).",
    )
    parser.add_argument("--k-cases", type=int, default=DEFAULT_K_CASES)
    parser.add_argument("--k-policies", type=int, default=DEFAULT_K_POLICIES)
    parser.add_argument(
        "--all-lifecycles",
        action="store_true",
        help="Do not restrict policies to lifecycle=published.",
    )
    parser.add_argument("--json", action="store_true", help="Print machine-readable JSON.")
    args = parser.parse_args()

    try:
        if args.leg != "hybrid":
            return _run_single_leg(args)

        result = retrieve(
            args.query,
            departments=args.department,
            k_cases=args.k_cases,
            k_policies=args.k_policies,
            published_only=not args.all_lifecycles,
        )
    except Exception:
        logger.exception("Retrieval probe failed")
        return 1

    if args.json:
        print(json.dumps(result.model_dump(), default=str))
        return 0

    print(f"queries={result.queries} departments={result.departments}")
    _print_group("cases", result.cases)
    _print_group("policies", result.policies)
    return 0


if __name__ == "__main__":
    sys.exit(main())
