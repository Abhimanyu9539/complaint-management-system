"""Idempotently create the Qdrant collection the ingestion pipeline writes into.

The vector index is derived, rebuildable state (build.md §0.5) — but its *shape*
is schema, so it is created by a versioned script rather than dashboard clicks,
exactly like the SQL migrations in supabase/migrations/.

Creates `complaint_kb_v1` with:
  - named dense vector  `dense`  — 1536 dims, cosine (text-embedding-3-small)
  - named sparse vector `sparse` — IDF modifier, for BM25 via fastembed
  - keyword payload indexes on the four filterable fields

Payload indexes are on dotted paths (`metadata.doc_id`, ...) because
`langchain_qdrant.QdrantVectorStore` nests all metadata under a `metadata` key.
See app/services/vector_store.py for the full explanation.

Safe to re-run: an existing collection is left untouched and index creation is
a server-side no-op when the index already matches.

Usage (cwd must be backend/ — config.py loads a relative ".env"):

    uv run python scripts/create_qdrant_collection.py
"""

import logging
import sys
from pathlib import Path

# Running a file inside scripts/ puts scripts/ on sys.path, not backend/, and the
# project is not pip-installed — so make `app` importable before importing it.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

# Importing from `app` first runs app/__init__.py, which injects the OS trust
# store into ssl. That must happen before any HTTPS client is constructed.
from app.config import Settings, get_settings  # noqa: E402
from app.services.vector_store import (  # noqa: E402
    DENSE_VECTOR_NAME,
    INDEXED_PAYLOAD_FIELDS,
    SPARSE_VECTOR_NAME,
    get_qdrant_client,
)
from qdrant_client import QdrantClient, models  # noqa: E402

logger = logging.getLogger("create_qdrant_collection")


def create_collection(client: QdrantClient, settings: Settings) -> bool:
    """Create the collection if absent. Returns True if it was created."""
    name = settings.qdrant_collection

    if client.collection_exists(name):
        logger.info("Collection '%s' already exists — skipping creation", name)
        return False

    try:
        client.create_collection(
            collection_name=name,
            vectors_config={
                DENSE_VECTOR_NAME: models.VectorParams(
                    size=settings.embedding_dims,
                    distance=models.Distance.COSINE,
                )
            },
            sparse_vectors_config={
                # IDF is required for BM25: without it Qdrant scores raw term
                # frequencies and sparse retrieval quietly degrades.
                SPARSE_VECTOR_NAME: models.SparseVectorParams(
                    modifier=models.Modifier.IDF
                )
            },
        )
    except Exception:
        logger.exception("Failed to create collection '%s'", name)
        raise

    logger.info(
        "Created collection '%s' (dense=%d dims cosine, sparse=BM25/IDF)",
        name,
        settings.embedding_dims,
    )
    return True


def create_payload_indexes(client: QdrantClient, settings: Settings) -> None:
    """Create a keyword index per filterable field.

    Each field is wrapped separately so one failure is logged and the rest still
    get created, rather than aborting the run halfway through.
    """
    name = settings.qdrant_collection

    for field in INDEXED_PAYLOAD_FIELDS:
        try:
            client.create_payload_index(
                collection_name=name,
                field_name=field,
                field_schema=models.PayloadSchemaType.KEYWORD,
            )
            logger.info("Payload index ensured: %s (keyword)", field)
        except Exception:
            logger.exception("Failed to create payload index on '%s'", field)


def log_collection_summary(client: QdrantClient, settings: Settings) -> None:
    """Read the collection back and log what Qdrant actually stored."""
    name = settings.qdrant_collection

    try:
        info = client.get_collection(name)
    except Exception:
        logger.exception("Failed to read back collection '%s'", name)
        raise

    params = info.config.params
    logger.info("--- '%s' as stored by Qdrant ---", name)
    logger.info("Dense vectors:  %s", params.vectors)
    logger.info("Sparse vectors: %s", params.sparse_vectors)
    logger.info("Payload indexes: %s", sorted(info.payload_schema or {}))
    logger.info("Points: %s", info.points_count)


def main() -> int:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)-8s %(name)s: %(message)s",
    )

    try:
        settings = get_settings()
        client = get_qdrant_client()

        create_collection(client, settings)
        create_payload_indexes(client, settings)
        log_collection_summary(client, settings)
    except Exception:
        logger.exception("Collection setup failed")
        return 1

    logger.info("Done.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
