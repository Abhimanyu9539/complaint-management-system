"""Create the Qdrant collections (`cms-create-collections`). Safe to re-run."""

import logging
import sys

# The `cms.config` import must come first: importing it runs cms/config/__init__.py,
# which injects the OS trust store into ssl. That has to happen before any HTTPS
# client is constructed.
from cms.config.logging_config import setup_logging
from cms.config.settings import get_settings
from cms.retrieval.vector_store.create_qdrant_collections import (
    ensure_collections,
)
from cms.retrieval.vector_store.qdrant_store import get_qdrant_client

logger = logging.getLogger("cms.cli.create_collections")


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
