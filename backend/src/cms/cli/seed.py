"""CLI entrypoint for the seed corpus ingest.

The run itself lives in `cms/ingestion/seed.py`; this file only parses arguments
and turns the summary into an exit code.

Usage (from anywhere, once the project is installed):

    cms-seed --one   # one case, the walking-skeleton gate
    cms-seed         # the full 25-document corpus

Where the corpus is read from, and how `.env` is located, are both
cwd-independent — see `cms.ingestion.seed.resolve_seed_dir` and
`cms.config.settings`.
"""

import argparse
import logging
import sys

# The `cms.config` import must come first: importing it runs cms/config/__init__.py,
# which injects the OS trust store into ssl. That has to happen before any HTTPS
# client (supabase, openai, qdrant, langsmith) is constructed.
from cms.config.logging_config import setup_logging
from cms.ingestion.seed import run_seed

logger = logging.getLogger("cms.cli.seed")


def main() -> int:
    setup_logging()

    parser = argparse.ArgumentParser(description="Ingest the synthetic seed corpus.")
    parser.add_argument(
        "--one",
        action="store_true",
        help="Ingest only the first case document (walking-skeleton check).",
    )
    args = parser.parse_args()

    try:
        summary = run_seed(one=args.one)
    except Exception:
        logger.exception("Seed run failed")
        return 1

    return 1 if summary.failed or summary.upload_failed else 0


if __name__ == "__main__":
    sys.exit(main())
