"""Ingest the seed corpus: `cms-seed` (everything), `--one` / `--one-policy` (one document), `--force`
(re-ingest unchanged documents too).
"""

import argparse
import asyncio
import logging
import sys

# The `cms.config` import must come first: importing it runs cms/config/__init__.py,
# which injects the OS trust store into ssl. That has to happen before any HTTPS
# client (supabase, openai, qdrant, langsmith) is constructed.
from cms.config.logging_config import setup_logging
from cms.ingestion.seed import run_seed

logger = logging.getLogger("cms.cli.seed")


def main() -> int:
    """Sync shell for the `[project.scripts]` entry point.

    Exactly one `asyncio.run` per process: the cached supabase and Qdrant
    clients bind their connection pools to the loop it creates.
    """
    return asyncio.run(_main())


async def _main() -> int:
    setup_logging()

    parser = argparse.ArgumentParser(description="Ingest the synthetic seed corpus.")
    parser.add_argument(
        "--one",
        action="store_true",
        help="Ingest only the first case document (walking-skeleton check).",
    )
    parser.add_argument(
        "--one-policy",
        action="store_true",
        help="Ingest only the first policy document (walking-skeleton check).",
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Re-ingest every document, bypassing the ingest-key short-circuit.",
    )
    args = parser.parse_args()

    try:
        summary = await run_seed(
            one=args.one, one_policy=args.one_policy, force=args.force
        )
    except Exception:
        logger.exception("Seed run failed")
        return 1

    return 1 if summary.failed or summary.upload_failed else 0


if __name__ == "__main__":
    sys.exit(main())
