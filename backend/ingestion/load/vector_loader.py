"""Embed chunk rows and upsert them into Qdrant, then clean up what they replaced.

Point ids are deterministic — `uuid5(namespace, "doc_id:index:chunk_hash")` —
which is idempotency layer 3: re-ingesting unchanged content overwrites the same
points instead of duplicating them.

The flip side of putting the chunk hash in the id is that *edited* text produces
a *new* id, so the point holding the old text would linger and stay retrievable.
That is why callers snapshot `existing_point_ids` before the upsert and pass the
difference to `delete_stale_points` after it.
"""

import logging
import uuid

from langchain_core.documents import Document
from qdrant_client import models

from retrieval.vector_store.qdrant_store import get_qdrant_client, get_vector_store

logger = logging.getLogger(__name__)

# Fixed namespace for point ids. Must never change: it is what makes a re-ingest
# of unchanged content land on the same points instead of duplicating them.
POINT_ID_NAMESPACE = uuid.UUID("6f3c9d4e-1b2a-5c8d-9e0f-7a1b2c3d4e5f")

# Qdrant scroll page size when listing a document's existing points.
_SCROLL_PAGE = 256


def build_point_id(document_id: str, chunk_index: int, chunk_hash: str) -> str:
    """Deterministic point id per build.md §0.4: uuid5(doc_id, index, hash)."""
    return str(uuid.uuid5(POINT_ID_NAMESPACE, f"{document_id}:{chunk_index}:{chunk_hash}"))


def existing_point_ids(collection_name: str, document_id: str) -> set[str]:
    """All point ids currently stored for this document in this collection."""
    client = get_qdrant_client()

    point_filter = models.Filter(
        must=[
            models.FieldCondition(
                key="metadata.doc_id",
                match=models.MatchValue(value=document_id),
            )
        ]
    )

    ids: set[str] = set()
    offset = None
    while True:
        points, offset = client.scroll(
            collection_name=collection_name,
            scroll_filter=point_filter,
            limit=_SCROLL_PAGE,
            offset=offset,
            with_payload=False,
            with_vectors=False,
        )
        ids.update(str(point.id) for point in points)
        if offset is None:
            break

    return ids


def upsert_points(
    collection_name: str,
    document_id: str,
    chunk_rows: list[dict],
    base_metadata: dict,
) -> list[str]:
    """Embed and write the points via LangChain, returning the point ids.

    `base_metadata` carries the document-level payload fields built by
    `ingestion.transform.enricher`; this function adds the per-chunk ones.

    `add_documents` batches the embedding calls internally, so a document costs
    one OpenAI round-trip rather than one per chunk — the silent cost/latency
    trap called out in steps.md §4.
    """
    documents: list[Document] = []
    point_ids: list[str] = []

    for row in chunk_rows:
        point_ids.append(
            build_point_id(document_id, row["chunk_index"], row["content_hash"])
        )
        documents.append(
            Document(
                page_content=row["text"],
                metadata={
                    **base_metadata,
                    "chunk_id": row["id"],
                    "chunk_index": row["chunk_index"],
                },
            )
        )

    get_vector_store(collection_name).add_documents(documents=documents, ids=point_ids)
    return point_ids


def delete_stale_points(
    collection_name: str, document_id: str, stale_ids: set[str]
) -> None:
    """Remove the points a previous version of this document left behind."""
    if not stale_ids:
        return

    client = get_qdrant_client()
    client.delete(
        collection_name=collection_name,
        points_selector=models.PointIdsList(points=sorted(stale_ids)),
    )
    logger.info(
        "Removed %d stale point(s) from a previous version of document %s in '%s'",
        len(stale_ids),
        document_id,
        collection_name,
    )
