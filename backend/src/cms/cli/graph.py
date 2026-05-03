"""CLI entrypoint for the graph probe: run one query through the compiled graph.

Usage (from anywhere, once the project is installed):

    cms-graph "my ProBlend 300 is showing ERR-22 and won't start"
    cms-graph "hey, what can you do?"
    cms-graph "refund for a delayed order" --json
    cms-graph "my order never arrived" --context

Prints the branch taken and, for a complaint, every reranked chunk retrieved
with the generated policy queries. `--context` prints the assembled context
block and citations instead — what the generate node will hand the model.
"""

import argparse
import asyncio
import json
import logging
import sys

# The `cms.config` import must come first: importing it runs cms/config/__init__.py,
# which injects the OS trust store into ssl. That has to happen before any HTTPS
# client (openai, supabase) is constructed.
from cms.config.logging_config import setup_logging  # isort: skip
from cms.cli.display import print_hits
from cms.rag.context import build_context
from cms.rag.graph import get_graph, route_by_intent

logger = logging.getLogger("cms.cli.graph")


def main() -> int:
    """Sync shell for the `[project.scripts]` entry point.

    Exactly one `asyncio.run` per process: the cached supabase and Qdrant
    clients bind their connection pools to the loop it creates.
    """
    return asyncio.run(_main())


async def _main() -> int:
    setup_logging()

    # Seeded policy text and model output are arbitrary UTF-8; Windows terminals
    # default stdout to the system codepage, which cannot encode most of it.
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")

    parser = argparse.ArgumentParser(
        description="Graph probe: analyze the query, then either reply to smalltalk or "
        "retrieve and rerank policy chunks. No generation yet."
    )
    parser.add_argument("query", help="The question or complaint text to run.")
    parser.add_argument("--json", action="store_true", help="Print machine-readable JSON.")
    parser.add_argument(
        "--context",
        action="store_true",
        help="Print the assembled context block and citations instead of chunk snippets.",
    )
    args = parser.parse_args()

    try:
        state = await get_graph().ainvoke({"query": args.query})
    except Exception:
        logger.exception("Graph probe failed")
        return 1

    branch = route_by_intent(state)
    hits = state.get("policy_hits", [])
    draft = state.get("draft")
    # Two different lists, and the difference is the point: `offered` is every
    # chunk the model was given, `cited` is the subset its draft actually used.
    offered_context, offered = build_context(hits) if args.context else ("", [])
    cited = state.get("citations", [])

    if args.json:
        print(
            json.dumps(
                {
                    "query": args.query,
                    "intent": state.get("intent"),
                    "branch": branch,
                    "policy_queries": state.get("policy_queries", []),
                    "draft": draft,
                    "context": offered_context if args.context else None,
                    "citations": [citation.model_dump() for citation in cited],
                    "hits": [
                        {"score": score, "text": document.page_content, **document.metadata}
                        for document, score in hits
                    ],
                },
                default=str,
            )
        )
        return 0

    print(f"query={args.query!r}")
    print(f"intent: {state.get('intent')} -> {branch}")

    queries = state.get("policy_queries", [])
    if queries:
        print(f"\npolicy queries ({len(queries)}):")
        for query in queries:
            suffix = "   <- original" if query == args.query else ""
            print(f"  - {query}{suffix}")

    if hits:
        print(f"\n{len(hits)} chunk(s) retrieved")
        if args.context:
            # Exactly what generate was handed, verbatim.
            print(f"\n--- context offered ({len(offered)} chunk(s)) ---\n")
            print(offered_context)
        else:
            print_hits(hits)

    if draft:
        print(f"\n--- draft ---\n{draft}")

    # Printed after the draft so the markers above are still on screen. Fewer
    # than the chunks offered is the normal, healthy case.
    if cited:
        print(f"\n--- cited ({len(cited)} of {len(hits)} offered) ---")
        for citation in cited:
            print(f"  [{citation.marker}] {citation.title} — {citation.section}")
            print(f"      doc_id={citation.doc_id} chunk_id={citation.chunk_id}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
