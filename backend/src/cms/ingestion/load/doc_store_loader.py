"""Build chunk rows and write them to Postgres — the source of truth for chunk text.

These rows are also what parent-document retrieval reads back: a Qdrant hit
carries a `chunk_id`, and that id resolves in Postgres to the full text plus its
position in the parent document.

The row *shape* is decided here; the SQL is `db.repositories.chunks`.
"""

import logging

from cms.db.repositories.chunks import delete_chunks_from, upsert_chunks
from cms.ingestion.transform.chunker import count_tokens
from cms.ingestion.transform.cleaner import compute_content_hash

logger = logging.getLogger(__name__)


async def write_chunks(
    chunk_table: str, fk_column: str, document_id: str, chunk_texts: list[str]
) -> list[dict]:
    """Upsert the chunk rows and return them (with ids) in chunk_index order."""
    rows = [
        {
            fk_column: document_id,
            "chunk_index": index,
            "text": text,
            "token_count": count_tokens(text),
            "content_hash": compute_content_hash(text),
        }
        for index, text in enumerate(chunk_texts)
    ]

    written = await upsert_chunks(chunk_table, fk_column, rows)

    if len(written) != len(rows):
        raise RuntimeError(
            f"Expected {len(rows)} chunk rows back from upsert, got {len(written)}"
        )

    # Drop the tail a shorter re-ingest left behind — see the repository.
    await delete_chunks_from(chunk_table, fk_column, document_id, len(rows))

    logger.debug(
        "Wrote %d chunk row(s) to %s for document %s",
        len(written),
        chunk_table,
        document_id,
    )
    return written
