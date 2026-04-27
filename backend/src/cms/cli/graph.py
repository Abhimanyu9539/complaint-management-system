"""CLI entrypoint for the graph probe: run one query through the compiled graph.

Usage (from anywhere, once the project is installed):

    cms-graph "my ProBlend 300 is showing ERR-22 and won't start"
    cms-graph "hey, what can you do?"
    cms-graph "refund for a delayed order" --json

Prints the branch taken and, for a complaint, every chunk retrieved with the
generated policy queries. No reranking on this path yet.
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
        "retrieve policy chunks — no reranking, no generation."
    )
    parser.add_argument("query", help="The question or complaint text to run.")
    parser.add_argument("--json", action="store_true", help="Print machine-readable JSON.")
    args = parser.parse_args()

    try:
        state = await get_graph().ainvoke({"query": args.query})
    except Exception:
        logger.exception("Graph probe failed")
        return 1

    branch = route_by_intent(state)
    hits = state.get("policy_hits", [])

    if args.json:
        print(
            json.dumps(
                {
                    "query": args.query,
                    "intent": state.get("intent"),
                    "branch": branch,
                    "policy_queries": state.get("policy_queries", []),
                    "draft": state.get("draft"),
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

    if state.get("draft"):
        print(f"\n{state['draft']}")
        return 0

    queries = state.get("policy_queries", [])
    print(f"policy queries ({len(queries)}):")
    for query in queries:
        suffix = "   <- original" if query == args.query else ""
        print(f"  - {query}{suffix}")

    print(f"\n{len(hits)} chunk(s)")
    print_hits(hits)
    return 0


if __name__ == "__main__":
    sys.exit(main())
