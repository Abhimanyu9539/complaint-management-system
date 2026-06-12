"""CLI entrypoint for the standalone `classify_ticket` probe.

Usage (from anywhere, once the project is installed):

    cms-classify "X200 stopped charging" "My X200 stopped charging after 3 months..."
    cms-classify "Charged twice" "Two charges of 249 for order #6120" --json
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
from cms.config.settings import get_settings
from cms.rag.nodes.classify_ticket import classify_ticket_core

logger = logging.getLogger("cms.cli.classify")


def main() -> int:
    """Sync shell for the `[project.scripts]` entry point.

    Exactly one `asyncio.run` per process: the cached supabase client binds its
    connection pool to the loop it creates.
    """
    return asyncio.run(_main())


async def _main() -> int:
    setup_logging()

    # Model output is arbitrary UTF-8; Windows terminals default stdout to the
    # system codepage, which cannot encode most of it.
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")

    parser = argparse.ArgumentParser(
        description="Standalone classify_ticket probe: department, severity, category, "
        "entities — no retrieval, no graph."
    )
    parser.add_argument("subject", help="The ticket subject.")
    parser.add_argument("body", help="The complaint text.")
    parser.add_argument("--json", action="store_true", help="Print machine-readable JSON.")
    args = parser.parse_args()

    try:
        result = await classify_ticket_core(args.subject, args.body)
    except Exception:
        logger.exception("classify_ticket probe failed")
        return 1

    if args.json:
        print(json.dumps(result.model_dump(), default=str))
        return 0

    floor = get_settings().routing_confidence_floor
    route = "routes directly" if result.confidence >= floor else "below floor -> human review"
    print(f"department: {result.department} ({result.confidence:.0%}) — {route}")
    runner_ups = " · ".join(f"{c.department} ({c.score:.0%})" for c in result.candidates[1:])
    print(f"also considered: {runner_ups or 'none'}")
    print(f"suggested severity: {result.suggested_severity}")
    print(f"category: {result.category}")
    entities = {k: v for k, v in result.entities.model_dump().items() if v}
    print(f"entities: {entities or 'none'}")
    print(f"reason: {result.reason}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
