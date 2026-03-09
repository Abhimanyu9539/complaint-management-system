"""CLI entrypoint for creating the Qdrant collections.

The collections' shape and the code that applies it live in
`retrieval/vector_store/create_qdrant_collections.py`; this file only wires a
client to it and turns the outcome into an exit code.

Safe to re-run: an existing collection is left untouched and index creation is
a server-side no-op when the index already matches.

Usage (cwd must be backend/ — config/settings.py loads a relative ".env"):

    uv run python scripts/create_qdrant_collection.py
"""

import logging
import sys
from pathlib import Path

# Running a file inside scripts/ puts scripts/ on sys.path, not backend/, and the
# project is not pip-installed — so make the packages importable before importing them.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

# The `config` import must come first: importing it runs config/__init__.py, which
# injects the OS trust store into ssl. That has to happen before any HTTPS client
# is constructed.
from config.logging_config import setup_logging  # noqa: E402
from config.settings import get_settings  # noqa: E402
from retrieval.vector_store.qdrant_store import get_qdrant_client  # noqa: E402
from retrieval.vector_store.create_qdrant_collections import (  # noqa: E402
    ensure_collections,
)

logger = logging.getLogger("create_qdrant_collection")


def main() -> int:
    setup_logging()

    try:
        succeeded = ensure_collections(get_qdrant_client(), get_settings())
    except Exception:
        logger.exception("Collection setup failed")
        return 1

    if not succeeded:
        return 1

    logger.info("Done.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
