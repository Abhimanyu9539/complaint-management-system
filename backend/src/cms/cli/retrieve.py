"""CLI entrypoint for the standalone policy retrieval probe.
Usage (from anywhere, once the project is installed):

    cms-retrieve "how long is the warranty period on a replacement unit" --corpus policies --mode dense
    cms-retrieve "refund for a delayed order" -k 8 --json
    cms-retrieve "CarePlan+" --mode sparse
    cms-retrieve "my X200 vacuum stopped charging" --corpus cases

Policies are reranked by default (Voyage via OpenRouter). `--no-rerank` gives the
raw candidate pool, and `--compare` prints both so the rerank can be judged by eye:

    cms-retrieve "how long is the warranty period" --compare
"""

import argparse
import asyncio
import json
import logging
import sys

from langchain_core.documents import Document

from cms.config.logging_config import setup_logging
from cms.retrieval.retrievers.case_retriever import (
    retrieve_cases_dense,
    retrieve_cases_hybrid,
    retrieve_cases_sparse,
)
from cms.retrieval.retrievers.policy_retriever import (
    DEFAULT_K,
    DEFAULT_TOP_N,
    RERANK_ENABLED,
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
# Only the policy retrievers take the rerank arguments.
RERANKABLE_CORPUS = "policies"

# Enough of a chunk to recognise it, short enough to keep one hit on a few lines.
SNIPPET_CHARS = 220


def _snippet(text: str) -> str:
    """One-line preview of a chunk: whitespace collapsed, then truncated."""
    flat = " ".join(text.split())
    return flat if len(flat) <= SNIPPET_CHARS else f"{flat[:SNIPPET_CHARS]}…"


def _key(document: Document) -> tuple:
    """Identity of a chunk, for matching a reranked hit back to its original rank.

    Falls back to the text: `doc_id` is always set by the ingest pipeline, but a
    hand-built Document in a probe need not have one.
    """
    metadata = document.metadata
    return (metadata.get("doc_id"), metadata.get("chunk_index"), document.page_content)


def _as_json(hits: list[tuple[Document, float]], ranks: dict | None = None) -> list[dict]:
    entries = []
    for document, score in hits:
        entry = {"score": score, "text": document.page_content, **document.metadata}
        if ranks is not None:
            entry["was_rank"] = ranks.get(_key(document))
        entries.append(entry)
    return entries


def _print_hits(hits: list[tuple[Document, float]], ranks: dict | None = None) -> None:
    for rank, (document, score) in enumerate(hits, start=1):
        metadata = document.metadata
        # Where this chunk sat before the rerank — a survivor from #14 is the
        # clearest evidence the reranker is doing something.
        moved = ""
        if ranks is not None:
            was = ranks.get(_key(document))
            moved = f"  (was #{was})" if was else "  (new)"
        print(f"\n{rank}. score={score:.4f}{moved}  {metadata.get('title')}")
        print(f"   doc_id={metadata.get('doc_id')} chunk={metadata.get('chunk_index')}")
        print(f"   {_snippet(document.page_content)}")


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
        help=f"How many chunks to retrieve (default: {DEFAULT_K}). With reranking on "
        "this is the candidate pool, not what you get back.",
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
    # Defaults are None, not the settings values, so "was this flag given?" stays
    # answerable — that is what makes the `--corpus cases` guard below possible.
    parser.add_argument(
        "--rerank",
        action=argparse.BooleanOptionalAction,
        default=None,
        help=f"Rerank the candidates via OpenRouter. Policies only. Default: {RERANK_ENABLED} "
        "(RERANK_ENABLED).",
    )
    parser.add_argument(
        "--top-n",
        type=int,
        default=None,
        help=f"How many chunks survive the rerank (default: {DEFAULT_TOP_N}).",
    )
    parser.add_argument(
        "--compare",
        action="store_true",
        help="Retrieve both ways and print the raw pool then the reranked one, with "
        "each survivor's original rank. Policies only.",
    )
    parser.add_argument("--json", action="store_true", help="Print machine-readable JSON.")
    args = parser.parse_args()

    # Caught here rather than in Qdrant, where it surfaces as an opaque 400.
    if args.top_k < 1:
        parser.error("--top-k must be at least 1")
    if args.top_n is not None and args.top_n < 1:
        parser.error("--top-n must be at least 1")
    if args.corpus != RERANKABLE_CORPUS and (
        args.rerank is not None or args.top_n is not None or args.compare
    ):
        parser.error(
            f"--rerank, --top-n and --compare apply to --corpus {RERANKABLE_CORPUS} only"
        )

    retrieve = RETRIEVERS[args.corpus][args.mode]
    rerank = RERANK_ENABLED if args.rerank is None else args.rerank
    top_n = DEFAULT_TOP_N if args.top_n is None else args.top_n

    try:
        if args.corpus != RERANKABLE_CORPUS:
            hits = await retrieve(args.query, k=args.top_k)
            baseline = None
        elif args.compare:
            # Two calls on purpose: one Qdrant round trip each, but it keeps the
            # baseline exactly the path `--no-rerank` takes rather than a
            # reconstruction of it.
            baseline = await retrieve(args.query, k=args.top_k, rerank=False)
            hits = await retrieve(
                args.query, k=args.top_k, rerank=True, top_n=top_n
            )
        else:
            baseline = None
            hits = await retrieve(args.query, k=args.top_k, rerank=rerank, top_n=top_n)
    except Exception:
        logger.exception("Retrieval probe failed")
        return 1

    ranks = (
        {_key(document): rank for rank, (document, _) in enumerate(baseline, start=1)}
        if baseline is not None
        else None
    )

    if args.json:
        payload = (
            {"baseline": _as_json(baseline), "reranked": _as_json(hits, ranks)}
            if baseline is not None
            else _as_json(hits)
        )
        print(json.dumps(payload, default=str))
        return 0

    print(f"query={args.query!r} corpus={args.corpus} mode={args.mode}")
    if baseline is not None:
        print(f"\n--- baseline (no rerank), {len(baseline)} hit(s) ---")
        _print_hits(baseline)
        print(f"\n--- reranked to top {top_n}, {len(hits)} hit(s) ---")
        _print_hits(hits, ranks)
        return 0

    print(f"{len(hits)} hit(s)")
    _print_hits(hits)
    return 0


if __name__ == "__main__":
    sys.exit(main())
