"""The shape of the two Qdrant collections, and the code that creates them.

LangChain nests all metadata under `metadata`, so every payload index and filter uses `metadata.<field>`;
a filter on the bare name silently matches nothing.
"""

import logging
from dataclasses import dataclass

from qdrant_client import QdrantClient, models

from cms.config.settings import Settings

logger = logging.getLogger(__name__)

# Named vectors. LangChain's defaults ("" and "langchain-sparse") can be overridden,
# so the clearer names are used.
DENSE_VECTOR_NAME = "dense"
SPARSE_VECTOR_NAME = "sparse"

# Fields retrieval filters on, as dotted paths into `metadata`. Split per
# collection: cases filter on `category`, policies filter on `lifecycle` (so
# retrieval can restrict to `published` clauses inside Qdrant).
CASE_PAYLOAD_FIELDS: tuple[str, ...] = (
    "metadata.doc_id",
    "metadata.department",
    "metadata.category",
)
POLICY_PAYLOAD_FIELDS: tuple[str, ...] = (
    "metadata.doc_id",
    "metadata.department",
    "metadata.lifecycle",
)


@dataclass(frozen=True)
class CollectionSpec:
    """What to create — one per corpus."""

    name: str
    payload_fields: tuple[str, ...]


def collection_specs(settings: Settings) -> list[CollectionSpec]:
    """The full set of collections this project expects to exist."""
    return [
        CollectionSpec(settings.qdrant_cases_collection, CASE_PAYLOAD_FIELDS),
        CollectionSpec(settings.qdrant_policies_collection, POLICY_PAYLOAD_FIELDS),
    ]


def create_collection(
    client: QdrantClient, name: str, embedding_dims: int, *, recreate: bool = False
) -> bool:
    """Create the collection if absent. Returns True if it was created.

    `recreate` drops an existing collection first — the only way to change the
    vector size, since Qdrant cannot resize one in place. It destroys every
    point, so callers must follow it with a forced re-ingest.
    """
    if client.collection_exists(name):
        if not recreate:
            logger.info("Collection '%s' already exists — skipping creation", name)
            return False

        logger.warning(
            "Dropping collection '%s' — every point is deleted and must be re-ingested",
            name,
        )
        client.delete_collection(name)

    try:
        client.create_collection(
            collection_name=name,
            vectors_config={
                DENSE_VECTOR_NAME: models.VectorParams(
                    size=embedding_dims,
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
        embedding_dims,
    )
    return True


def create_payload_indexes(
    client: QdrantClient, name: str, payload_fields: tuple[str, ...]
) -> None:
    """Create a keyword index per filterable field.

    Each field is wrapped separately so one failure is logged and the rest still
    get created, rather than aborting the run halfway through.
    """
    for field in payload_fields:
        try:
            client.create_payload_index(
                collection_name=name,
                field_name=field,
                field_schema=models.PayloadSchemaType.KEYWORD,
            )
            logger.info("Payload index ensured on '%s': %s (keyword)", name, field)
        except Exception:
            logger.exception("Failed to create payload index on '%s'.'%s'", name, field)


def log_collection_summary(client: QdrantClient, name: str) -> None:
    """Read the collection back and log what Qdrant actually stored."""
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


def ensure_collection(
    client: QdrantClient, settings: Settings, spec: CollectionSpec, *, recreate: bool = False
) -> None:
    """Bring one collection up to spec, then log what Qdrant stored."""
    create_collection(client, spec.name, settings.embedding_dims, recreate=recreate)
    create_payload_indexes(client, spec.name, spec.payload_fields)
    log_collection_summary(client, spec.name)


def ensure_collections(
    client: QdrantClient, settings: Settings, *, recreate: bool = False
) -> bool:
    """Bring every collection up to spec. Returns True if all of them succeeded.

    Safe to re-run: an existing collection is left untouched and index creation
    is a server-side no-op when the index already matches. `recreate` opts out
    of that safety to apply a new vector size — see `create_collection`.

    Each collection is isolated — a failure setting up one should not prevent
    the other from being attempted and reported.
    """
    succeeded = True
    for spec in collection_specs(settings):
        try:
            ensure_collection(client, settings, spec, recreate=recreate)
        except Exception:
            logger.exception("Collection setup failed for '%s'", spec.name)
            succeeded = False
    return succeeded
