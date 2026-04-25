"""CLI entrypoint for the standalone policy retrieval probe.
Usage (from anywhere, once the project is installed):

    cms-retrieve "how long is the warranty period on a replacement unit" --corpus policies --mode dense
    cms-retrieve "refund for a delayed order" -k 8 --json
    cms-retrieve "CarePlan+" --mode sparse
    cms-retrieve "my X200 vacuum stopped charging" --corpus cases
"""

import argparse
import asyncio
import json
import logging
import sys

from cms.config.logging_config import setup_logging
from cms.retrieval.retrievers.case_retriever import (
    retrieve_cases_dense,
    retrieve_cases_hybrid,
    retrieve_cases_sparse,
)
from cms.retrieval.retrievers.policy_retriever import (
    DEFAULT_K,
    retrieve_policies_dense,
    retrieve_policies_hybrid,
    retrieve_policies_sparse,
)

logger = logging.getLogger("cms.cli.retrieve")

RETRIEVERS = {
    "policies": {
        "dense": retrieve_policies_dense,
        "sparse": retrieve_policies_sparse,
        "hybrid": retrieve_policies_hybrid,
    },
    "cases": {
        "dense": retrieve_cases_dense,
        "sparse": retrieve_cases_sparse,
        "hybrid": retrieve_cases_hybrid,
    },
}
DEFAULT_CORPUS = "policies"
DEFAULT_MODE = "hybrid"

# Enough of a chunk to recognise it, short enough to keep one hit on a few lines.
SNIPPET_CHARS = 220


def _snippet(text: str) -> str:
    """One-line preview of a chunk: whitespace collapsed, then truncated."""
    flat = " ".join(text.split())
    return flat if len(flat) <= SNIPPET_CHARS else f"{flat[:SNIPPET_CHARS]}…"


def main() -> int:
    """Sync shell for the `[project.scripts]` entry point.

    Exactly one `asyncio.run` per process: the cached supabase and Qdrant
    clients bind their connection pools to the loop it creates.
    """
    return asyncio.run(_main())


async def _main() -> int:
    setup_logging()

    # Seeded policy text is arbitrary UTF-8; Windows terminals default stdout to
    # the system codepage, which cannot encode most of it.
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")

    parser = argparse.ArgumentParser(
        description="Standalone retrieval probe: dense, sparse or hybrid top-k search "
        "over the policy or case chunks — no graph, no generation."
    )
    parser.add_argument("query", help="The question to retrieve chunks for.")
    parser.add_argument(
        "-k",
        "--top-k",
        type=int,
        default=DEFAULT_K,
        help=f"How many chunks to return (default: {DEFAULT_K}).",
    )
    parser.add_argument(
        "--corpus",
        choices=sorted(RETRIEVERS),
        default=DEFAULT_CORPUS,
        help=f"Which collection to search. Default: {DEFAULT_CORPUS}.",
    )
    parser.add_argument(
        "--mode",
        # Both corpora expose the same three legs, so derive the choices from one.
        choices=sorted(RETRIEVERS[DEFAULT_CORPUS]),
        default=DEFAULT_MODE,
        help="Which leg to run: dense (cosine), sparse (BM25), or hybrid (both, fused "
        f"by Qdrant). Default: {DEFAULT_MODE}.",
    )
    parser.add_argument("--json", action="store_true", help="Print machine-readable JSON.")
    args = parser.parse_args()

    # Caught here rather than in Qdrant, where it surfaces as an opaque 400.
    if args.top_k < 1:
        parser.error("--top-k must be at least 1")

    try:
        hits = await RETRIEVERS[args.corpus][args.mode](args.query, k=args.top_k)
    except Exception:
        logger.exception("Retrieval probe failed")
        return 1

    if args.json:
        print(
            json.dumps(
                [
                    {"score": score, "text": document.page_content, **document.metadata}
                    for document, score in hits
                ],
                default=str,
            )
        )
        return 0

    print(f"query={args.query!r} corpus={args.corpus} mode={args.mode}")
    print(f"{len(hits)} hit(s)")
    for rank, (document, score) in enumerate(hits, start=1):
        metadata = document.metadata
        print(f"\n{rank}. score={score:.4f}  {metadata.get('title')}")
        print(f"   doc_id={metadata.get('doc_id')} chunk={metadata.get('chunk_index')}")
        print(f"   {_snippet(document.page_content)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
