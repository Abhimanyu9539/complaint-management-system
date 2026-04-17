"""CLI entrypoint for the standalone `analyze_query` probe.

steps.md's rationale for building nodes behind a CLI first: "every prompt
tweak is a 5-second re-run." This calls `analyze_query_core` directly — no
`GraphState`, no graph. The node logic lives in `cms.rag.nodes.analyze_query`;
this file only parses arguments, prints results, and turns the outcome into
an exit code.

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
from cms.rag.nodes.analyze_query import analyze_query_core

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
        description="Standalone analyze_query probe: intent, department, entities, "
        "rewritten search queries — no retrieval, no graph."
    )
    parser.add_argument("query", help="The question or complaint text to analyze.")
    parser.add_argument("--json", action="store_true", help="Print machine-readable JSON.")
    args = parser.parse_args()

    try:
        analysis = await analyze_query_core(args.query)
    except Exception:
        logger.exception("analyze_query probe failed")
        return 1

    if args.json:
        print(json.dumps(analysis.model_dump(), default=str))
        return 0

    print(f"query={args.query!r}")
    print(f"intent: {analysis.intent}")
    print("department candidates:")
    for candidate in analysis.department_candidates:
        print(f"  {candidate.department}: {candidate.confidence:.2f}")
    print(f"entities: {analysis.entities}")
    print("search queries:")
    for query in analysis.search_queries:
        print(f"  - {query}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
