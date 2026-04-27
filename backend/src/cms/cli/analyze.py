"""CLI entrypoint for the standalone `analyze_query` probe.

Usage (from anywhere, once the project is installed):

    cms-analyze "my ProBlend 300 is showing ERR-22 and won't start"
    cms-analyze "what can you do?" --json
"""

import argparse
import asyncio
import json
import logging
import sys

# The `cms.config` import must come first: importing it runs cms/config/__init__.py,
# which injects the OS trust store into ssl. That has to happen before any HTTPS
# client (openai, supabase) is constructed.
from cms.config.logging_config import setup_logging
from cms.rag.nodes.analyze_query import analyze_query_core, build_policy_queries

logger = logging.getLogger("cms.cli.analyze")


def main() -> int:
    """Sync shell for the `[project.scripts]` entry point.

    Exactly one `asyncio.run` per process: the cached supabase and Qdrant
    clients bind their connection pools to the loop it creates.
    """
    return asyncio.run(_main())


async def _main() -> int:
    setup_logging()

    # Seeded/uploaded text and model output are arbitrary UTF-8; Windows
    # terminals default stdout to the system codepage, which cannot encode
    # most of it.
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")

    parser = argparse.ArgumentParser(
        description="Standalone analyze_query probe: intent and policy queries — "
        "no retrieval, no graph."
    )
    parser.add_argument("query", help="The question or complaint text to analyze.")
    parser.add_argument("--json", action="store_true", help="Print machine-readable JSON.")
    args = parser.parse_args()

    try:
        analysis = await analyze_query_core(args.query)
    except Exception:
        logger.exception("analyze_query probe failed")
        return 1

    queries = build_policy_queries(args.query, analysis)

    if args.json:
        print(json.dumps({**analysis.model_dump(), "policy_queries": queries}, default=str))
        return 0

    print(f"query={args.query!r}")
    print(f"intent: {analysis.intent}")
    print(f"policy queries ({len(queries)}):")
    for query in queries:
        suffix = "   <- original" if query == args.query else ""
        print(f"  - {query}{suffix}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
