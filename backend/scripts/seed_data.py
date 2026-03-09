"""CLI entrypoint for the seed corpus ingest.

The run itself lives in `ingestion/seed.py`; this file only parses arguments and
turns the summary into an exit code.

Usage (cwd must be backend/ — config/settings.py loads a relative ".env"):

    uv run python scripts/seed_data.py --one   # one case, the walking-skeleton gate
    uv run python scripts/seed_data.py         # the full 25-document corpus
"""

import argparse
import logging
import sys
from pathlib import Path

# Running a file inside scripts/ puts scripts/ on sys.path, not backend/, and the
# project is not pip-installed — so make the packages importable before importing them.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

# The `config` import must come first: importing it runs config/__init__.py, which
# injects the OS trust store into ssl. That has to happen before any HTTPS client
# (supabase, openai, qdrant, langsmith) is constructed.
from config.logging_config import setup_logging  # noqa: E402
from ingestion.seed import run_seed  # noqa: E402

logger = logging.getLogger("seed_data")


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

    return 1 if summary.failed else 0


if __name__ == "__main__":
    sys.exit(main())
