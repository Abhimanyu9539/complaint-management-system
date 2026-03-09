"""Reads and writes of the two chunk tables — `case_chunks` and `policy_chunks`.

Parameterised by table and foreign-key column rather than split in two, unlike
the parent tables: the chunk tables have identical shapes and no reason to
diverge, so two copies would be duplication with nothing behind it.
"""

import logging

from db.session import get_supabase

logger = logging.getLogger(__name__)


def upsert_chunks(chunk_table: str, fk_column: str, rows: list[dict]) -> list[dict]:
    """Upsert chunk rows, returning them (with ids) in chunk_index order.

    Conflicting on `(fk_column, chunk_index)` is what makes a re-ingest update
    rows in place instead of appending a second copy of the document.
    """
    response = (
        get_supabase()
        .table(chunk_table)
        .upsert(rows, on_conflict=f"{fk_column},chunk_index")
        .execute()
    )
    return sorted(response.data, key=lambda row: row["chunk_index"])


def delete_chunks_from(
    chunk_table: str, fk_column: str, document_id: str, start_index: int
) -> None:
    """Delete this document's chunks at or beyond `start_index`.

    Needed when a document shrank on re-ingest: without this, the tail of the
    previous version survives as orphaned rows pointing at content that no
    longer exists.
    """
    get_supabase().table(chunk_table).delete().eq(fk_column, document_id).gte(
        "chunk_index", start_index
    ).execute()
