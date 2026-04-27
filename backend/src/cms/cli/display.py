"""Printing retrieved chunks, shared by the CLI probes that show them.
"""

from langchain_core.documents import Document

# Enough of a chunk to recognise it, short enough to keep one hit on a few lines.
SNIPPET_CHARS = 220


def snippet(text: str) -> str:
    """One-line preview of a chunk: whitespace collapsed, then truncated."""
    flat = " ".join(text.split())
    return flat if len(flat) <= SNIPPET_CHARS else f"{flat[:SNIPPET_CHARS]}…"


def chunk_key(document: Document) -> tuple:
    """Identity of a chunk, for matching a reranked hit back to its original rank.

    Falls back to the text: `doc_id` is always set by the ingest pipeline, but a
    hand-built Document in a probe need not have one.
    """
    metadata = document.metadata
    return (metadata.get("doc_id"), metadata.get("chunk_index"), document.page_content)


def print_hits(hits: list[tuple[Document, float]], ranks: dict | None = None) -> None:
    """Rank, score, title, ids and a snippet per hit; `ranks` adds pre-rerank position."""
    for rank, (document, score) in enumerate(hits, start=1):
        metadata = document.metadata
        # Where this chunk sat before the rerank — a survivor from #14 is the
        # clearest evidence the reranker is doing something.
        moved = ""
        if ranks is not None:
            was = ranks.get(chunk_key(document))
            moved = f"  (was #{was})" if was else "  (new)"
        print(f"\n{rank}. score={score:.4f}{moved}  {metadata.get('title')}")
        print(f"   doc_id={metadata.get('doc_id')} chunk={metadata.get('chunk_index')}")
        print(f"   {snippet(document.page_content)}")
