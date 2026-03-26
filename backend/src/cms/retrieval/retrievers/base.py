"""Shared types for the retriever legs and their hybrid composition.

One `RetrievedChunk` shape crosses every layer in `retrieval.retrievers` — the
dense leg, the sparse leg, and the hybrid fusion over both — so a caller (the
future `retrieve` graph node, the CLI probe) never has to know which layer
produced a given chunk.
"""

import logging
from typing import Literal

from langchain_core.documents import Document
from pydantic import BaseModel, ConfigDict, Field

logger = logging.getLogger(__name__)

Corpus = Literal["case", "policy"]


class RetrievedChunk(BaseModel):
    """One retrieved chunk, with the payload fields citations and filtering need.

    `score` is deliberately unitless in this type: it is a cosine similarity
    when produced by the dense leg, a BM25 score when produced by the sparse
    leg, and a reciprocal-rank-fusion score when produced by
    `hybrid_retriever.rrf_fuse`. These are never comparable across legs or
    across collections (cases and policies calibrate BM25 IDF independently —
    see `qdrant_store`'s module docstring). That is exactly why fusion in this
    package works by *rank*, not by raw score.

    `frozen=True` matches the convention in `schemas/admin.py`: a retrieved
    chunk is a value, not something a node should mutate after the fact — the
    fused score `rrf_fuse` writes in is created via `model_copy`, not a set.
    """

    model_config = ConfigDict(frozen=True)

    point_id: str
    chunk_id: str | None
    doc_id: str | None
    corpus: Corpus
    text: str
    title: str | None
    department: str | None
    score: float
    metadata: dict = Field(default_factory=dict)


def to_chunk(document: Document, score: float, corpus: Corpus) -> RetrievedChunk:
    """Map one LangChain `Document` (as returned by `similarity_search_with_score`)
    onto our `RetrievedChunk`.

    Every field but `text`/`score`/`corpus` is read with `.get`: a point written
    before a metadata field existed (or written by a future ingest path that
    doesn't set every key) must degrade to `None` rather than raise — a missing
    title is a display nit, not a reason to drop the evidence.
    """
    metadata = document.metadata or {}
    return RetrievedChunk(
        point_id=str(metadata.get("_id", "")),
        chunk_id=metadata.get("chunk_id"),
        doc_id=metadata.get("doc_id"),
        corpus=corpus,
        text=document.page_content,
        title=metadata.get("title"),
        department=metadata.get("department"),
        score=score,
        metadata=metadata,
    )
