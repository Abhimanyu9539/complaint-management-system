"""CLI entrypoint for a full re-index after a hyperparameter change.

Edit the knobs in `.env`, run this, then probe with `cms-retrieve`.

    cms-reindex          # recreate the collections at the current dims, re-embed everything
    cms-reindex --keep   # keep the collections as they are, just re-embed
"""

import argparse
import asyncio
import logging
import sys

# The `cms.config` import must come first: importing it runs cms/config/__init__.py,
# which injects the OS trust store into ssl. That has to happen before any HTTPS
# client (supabase, openai, qdrant, langsmith) is constructed.
from cms.config.logging_config import setup_logging
from cms.config.settings import Settings, get_settings
from cms.ingestion.seed import run_seed
from cms.retrieval.vector_store.create_qdrant_collections import ensure_collections
from cms.retrieval.vector_store.qdrant_store import get_qdrant_client

logger = logging.getLogger("cms.cli.reindex")


def log_hyperparams(settings: Settings) -> None:
    """Log what this run applies, so a sweep's logs say which config produced them."""
    logger.info("embedding:    %s (%d dims)", settings.embedding_model, settings.embedding_dims)
    logger.info(
        "policy chunk: %d tokens / %d overlap",
        settings.policy_chunk_tokens,
        settings.policy_chunk_overlap,
    )
    logger.info("top-k:        cases=%d policies=%d", settings.case_top_k, settings.policy_top_k)
    logger.info(
        "collections:  %s, %s",
        settings.qdrant_cases_collection,
        settings.qdrant_policies_collection,
    )


def main() -> int:
    """Sync shell for the `[project.scripts]` entry point.

    Exactly one `asyncio.run` per process: the cached supabase and Qdrant
    clients bind their connection pools to the loop it creates.
    """
    return asyncio.run(_main())


async def _main() -> int:
    setup_logging()

    parser = argparse.ArgumentParser(
        description="Re-embed the whole corpus against the current .env hyperparameters."
    )
    parser.add_argument(
        "--keep",
        action="store_true",
        help="Reuse the existing collections instead of dropping them. Skip the drop "
        "only when the vector size is unchanged.",
    )
    args = parser.parse_args()

    settings = get_settings()
    log_hyperparams(settings)

    # Collections first, and before anything opens a vector store: `get_vector_store`
    # is lru_cached and validates dimensions on construction, so a store opened
    # against the old collection would pin the old size for the rest of the process.
    try:
        if not ensure_collections(get_qdrant_client(), settings, recreate=not args.keep):
            return 1
    except Exception:
        logger.exception("Collection setup failed")
        return 1

    # force=True is not optional: dropping a collection wipes its points but
    # leaves `status='indexed'` in Postgres, so an unforced run would skip every
    # document and leave the collection empty.
    try:
        summary = await run_seed(force=True)
    except Exception:
        logger.exception("Re-index failed")
        return 1

    return 1 if summary.failed or summary.upload_failed else 0


if __name__ == "__main__":
    sys.exit(main())
