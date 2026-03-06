"""The ingestion pipeline: one document in, Postgres chunks + Qdrant points out.

The write order in `ingest_document` is the consistency protocol from
build.md §0.5 and is not arbitrary:

    chunk → write `chunks` rows → embed + upsert Qdrant points → mark indexed

Postgres before Qdrant, because Postgres is the source of truth and Qdrant is a
rebuildable cache of it. A crash in between leaves the document visibly stuck
at `status='processing'` and a re-run finishes the job. The reverse order would
leave Qdrant points that retrieval can find but Postgres cannot explain — ghost
chunks are the dangerous failure direction.

Idempotency has three layers, so re-running a seed or a retry is free and safe:
  1. content-hash short-circuit — unchanged documents cost zero OpenAI calls;
  2. `chunks` upsert on `(document_id, chunk_index)` — rows update in place;
  3. deterministic Qdrant point ids — points overwrite instead of duplicating.
"""

import hashlib
import logging
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone

from langchain_core.documents import Document
from langsmith import traceable
from qdrant_client import models

from app.config import get_settings
from app.ingestion.chunkers import chunk_document, count_tokens
from app.services.supabase_client import get_supabase
from app.services.vector_store import get_qdrant_client, get_vector_store

logger = logging.getLogger(__name__)

# Fixed namespace for point ids. Must never change: it is what makes a re-ingest
# of unchanged content land on the same points instead of duplicating them.
POINT_ID_NAMESPACE = uuid.UUID("6f3c9d4e-1b2a-5c8d-9e0f-7a1b2c3d4e5f")

# Ingest traces go to their own LangSmith project (build.md §0.3.3) so they do
# not bury the chat traces we actually read day to day.
INGEST_PROJECT = f"{get_settings().langsmith_project}-ingest"

# Qdrant scroll page size when listing a document's existing points.
_SCROLL_PAGE = 256


@dataclass
class IngestResult:
    """Outcome of one document ingest, for the caller's summary line."""

    document_id: str
    status: str  # "indexed" | "skipped"
    chunk_count: int
    point_count: int


def compute_content_hash(text: str) -> str:
    """Stable hash of a document's full text — the short-circuit key."""
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def build_point_id(document_id: str, chunk_index: int, chunk_hash: str) -> str:
    """Deterministic point id per build.md §0.4: uuid5(doc_id, index, hash)."""
    return str(uuid.uuid5(POINT_ID_NAMESPACE, f"{document_id}:{chunk_index}:{chunk_hash}"))


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _fetch_document(document_id: str) -> dict:
    supabase = get_supabase()
    response = (
        supabase.table("documents")
        .select("id,title,doc_type,department_id,category,source,status,content_hash")
        .eq("id", document_id)
        .execute()
    )
    if not response.data:
        raise LookupError(f"No documents row with id {document_id}")
    return response.data[0]


def _write_chunks(document_id: str, chunk_texts: list[str]) -> list[dict]:
    """Upsert the chunk rows and return them (with ids) in chunk_index order.

    Rows beyond the new chunk count are deleted: if a document shrank on
    re-ingest, the tail of the previous version would otherwise survive as
    orphaned rows pointing at content that no longer exists.
    """
    supabase = get_supabase()

    rows = [
        {
            "document_id": document_id,
            "chunk_index": index,
            "text": text,
            "token_count": count_tokens(text),
            "content_hash": compute_content_hash(text),
        }
        for index, text in enumerate(chunk_texts)
    ]

    response = (
        supabase.table("chunks")
        .upsert(rows, on_conflict="document_id,chunk_index")
        .execute()
    )
    written = sorted(response.data, key=lambda row: row["chunk_index"])

    if len(written) != len(rows):
        raise RuntimeError(
            f"Expected {len(rows)} chunk rows back from upsert, got {len(written)}"
        )

    supabase.table("chunks").delete().eq("document_id", document_id).gte(
        "chunk_index", len(rows)
    ).execute()

    return written


def _existing_point_ids(document_id: str) -> set[str]:
    """All point ids currently stored for this document.

    Needed because a point id embeds the chunk's content hash: edited text
    produces a *new* id, so the old point would linger and stay retrievable
    unless we explicitly remove it after the upsert.
    """
    client = get_qdrant_client()
    settings = get_settings()

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
            collection_name=settings.qdrant_collection,
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


def _upsert_points(document: dict, chunk_rows: list[dict]) -> list[str]:
    """Embed and write the points via LangChain, returning the point ids.

    `add_documents` batches the embedding calls internally, so a document costs
    one OpenAI round-trip rather than one per chunk — the silent cost/latency
    trap called out in steps.md §4.
    """
    documents: list[Document] = []
    point_ids: list[str] = []

    for row in chunk_rows:
        point_ids.append(
            build_point_id(document["id"], row["chunk_index"], row["content_hash"])
        )
        # Payload keys are build.md §0.4's table; QdrantVectorStore nests them
        # all under `metadata`, which is why filters use `metadata.department`.
        documents.append(
            Document(
                page_content=row["text"],
                metadata={
                    "doc_id": document["id"],
                    "chunk_id": row["id"],
                    "doc_type": document["doc_type"],
                    "department": document["department_id"],
                    "category": document["category"],
                    "title": document["title"],
                    "chunk_index": row["chunk_index"],
                    "source": document["source"],
                },
            )
        )

    get_vector_store().add_documents(documents=documents, ids=point_ids)
    return point_ids


def _delete_stale_points(document_id: str, stale_ids: set[str]) -> None:
    if not stale_ids:
        return

    client = get_qdrant_client()
    client.delete(
        collection_name=get_settings().qdrant_collection,
        points_selector=models.PointIdsList(points=sorted(stale_ids)),
    )
    logger.info(
        "Removed %d stale point(s) from a previous version of document %s",
        len(stale_ids),
        document_id,
    )


def _mark_failed(document_id: str, job_id: str | None, error: str) -> None:
    """Record the failure on both rows.

    Wrapped separately: if Postgres is what broke, this bookkeeping fails too,
    and it must not replace the original exception with a confusing second one.
    """
    try:
        supabase = get_supabase()
        supabase.table("documents").update(
            {"status": "failed", "error": error[:2000]}
        ).eq("id", document_id).execute()
        if job_id:
            supabase.table("ingestion_jobs").update(
                {"status": "failed", "error": error[:2000], "finished_at": _now()}
            ).eq("id", job_id).execute()
    except Exception:
        logger.exception("Could not record failure state for document %s", document_id)


@traceable(name="ingest_document", project_name=INGEST_PROJECT)
def ingest_document(document_id: str, raw_text: str) -> IngestResult:
    """Ingest one document end to end. Returns what happened; raises on failure."""
    supabase = get_supabase()
    document = _fetch_document(document_id)
    content_hash = compute_content_hash(raw_text)

    if document["status"] == "indexed" and document["content_hash"] == content_hash:
        logger.info(
            "Document %s ('%s') unchanged — skipping (no embedding cost)",
            document_id,
            document["title"],
        )
        return IngestResult(document_id, "skipped", 0, 0)

    job_id: str | None = None
    try:
        job = (
            supabase.table("ingestion_jobs")
            .insert(
                {
                    "document_id": document_id,
                    "status": "running",
                    "started_at": _now(),
                }
            )
            .execute()
        )
        job_id = job.data[0]["id"]

        supabase.table("documents").update({"status": "processing", "error": None}).eq(
            "id", document_id
        ).execute()

        chunk_texts = chunk_document(document["doc_type"], raw_text)
        chunk_rows = _write_chunks(document_id, chunk_texts)

        # Snapshot before writing, so the diff afterwards is exactly the points
        # the previous version left behind.
        previous_point_ids = _existing_point_ids(document_id)
        point_ids = _upsert_points(document, chunk_rows)
        _delete_stale_points(document_id, previous_point_ids - set(point_ids))

        supabase.table("documents").update(
            {
                "status": "indexed",
                "content_hash": content_hash,
                "chunk_count": len(chunk_rows),
                "indexed_at": _now(),
                "error": None,
            }
        ).eq("id", document_id).execute()

        supabase.table("ingestion_jobs").update(
            {
                "status": "done",
                "chunk_count": len(chunk_rows),
                "point_count": len(point_ids),
                "finished_at": _now(),
            }
        ).eq("id", job_id).execute()

    except Exception as exc:
        logger.exception("Ingest failed for document %s ('%s')", document_id, document["title"])
        _mark_failed(document_id, job_id, f"{type(exc).__name__}: {exc}")
        raise

    logger.info(
        "Indexed '%s' (%s): %d chunk(s), %d point(s)",
        document["title"],
        document["doc_type"],
        len(chunk_rows),
        len(point_ids),
    )
    return IngestResult(document_id, "indexed", len(chunk_rows), len(point_ids))
