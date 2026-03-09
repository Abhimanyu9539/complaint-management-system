"""The shape of the two Qdrant collections, and the code that creates it.

The vector index is derived, rebuildable state (build.md §0.5) — but its *shape*
is schema, so it is declared here and applied by a versioned entrypoint rather
than by dashboard clicks, exactly like the SQL migrations in
supabase/migrations/.

Cases and policies are separate corpora — separate Postgres tables, separate
write permissions, separate chunking — and that separation carries through to
retrieval as two collections rather than one collection filtered by a `doc_type`
field. The collection itself is the discriminator, so `doc_type` is not a
payload field in either collection.

Everything that touches vectors imports its vector names and indexed fields from
here, so the collections that get *created* and the collections that get
*written to* can never drift apart.

Payload layout
--------------
Writes and reads go through ``langchain_qdrant.QdrantVectorStore``, which
hardcodes its payload shape: chunk text under ``page_content``, all metadata
nested under a single ``metadata`` key. There is no flat-metadata option
(``metadata_payload_key`` renames the wrapper, it cannot remove it)::

    {
      "page_content": "<chunk text>",
      "metadata": {"doc_id": ..., "department": ..., ...}
    }

Consequence: every payload filter — and every index below — must use the dotted
path ``metadata.department``, never ``department``. Qdrant indexes and filters
nested paths natively, so this costs nothing at retrieval time, but a filter
written against the flat name silently matches zero points.

Takes its `QdrantClient` as an argument rather than importing one, so this
module stays a leaf: `qdrant_store` imports the names below, and a cycle would
form the moment this file imported back.
"""

import logging
from dataclasses import dataclass

from qdrant_client import QdrantClient, models

from cms.config.settings import Settings

logger = logging.getLogger(__name__)

# Named vectors, per build.md §0.4. LangChain's defaults ("" and
# "langchain-sparse") are accepted as constructor args, so we keep the clearer
# names rather than inheriting them.
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


def create_collection(client: QdrantClient, name: str, embedding_dims: int) -> bool:
    """Create the collection if absent. Returns True if it was created."""
    if client.collection_exists(name):
        logger.info("Collection '%s' already exists — skipping creation", name)
        return False

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
    client: QdrantClient, settings: Settings, spec: CollectionSpec
) -> None:
    """Bring one collection up to spec, then log what Qdrant stored."""
    create_collection(client, spec.name, settings.embedding_dims)
    create_payload_indexes(client, spec.name, spec.payload_fields)
    log_collection_summary(client, spec.name)


def ensure_collections(client: QdrantClient, settings: Settings) -> bool:
    """Bring every collection up to spec. Returns True if all of them succeeded.

    Safe to re-run: an existing collection is left untouched and index creation
    is a server-side no-op when the index already matches.

    Each collection is isolated — a failure setting up one should not prevent
    the other from being attempted and reported.
    """
    succeeded = True
    for spec in collection_specs(settings):
        try:
            ensure_collection(client, settings, spec)
        except Exception:
            logger.exception("Collection setup failed for '%s'", spec.name)
            succeeded = False
    return succeeded
