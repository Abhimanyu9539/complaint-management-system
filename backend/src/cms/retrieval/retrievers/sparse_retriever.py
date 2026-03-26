"""The lexical retrieval leg: sparse (BM25, local fastembed) search.

Exact-token matching — `ERR-22`, order `#4521`, model `X200` — which is what
complaint text is full of and dense embeddings handle poorly (build.md §0.4).
Mirrors `dense_retriever.dense_search`'s signature exactly so
`hybrid_retriever` can run both legs identically.

Two things worth stating because they are not obvious from the call site:

- **Zero API cost.** fastembed runs a local ONNX model; the first call in a
  process downloads it (~50 MB), which is why `get_sparse_embeddings` in
  `qdrant_store` is cached.
- **Depends on the collection's IDF modifier.** These scores are only
  meaningful because `create_qdrant_collections.create_collection` declared
  `models.Modifier.IDF` on the sparse vector — without it Qdrant would score
  raw term frequency and this leg would quietly degrade rather than fail. IDF
  is computed *per collection*, so sparse scores from `cases_v1` and
  `policies_v1` are never comparable to each other.
"""

import logging

from langchain_qdrant import RetrievalMode
from qdrant_client import models

from cms.retrieval.retrievers.base import Corpus, RetrievedChunk, to_chunk
from cms.retrieval.vector_store.qdrant_store import get_vector_store

logger = logging.getLogger(__name__)


def sparse_search(
    collection_name: str,
    query: str,
    corpus: Corpus,
    k: int,
    query_filter: models.Filter | None,
) -> list[RetrievedChunk]:
    """Top-`k` sparse (BM25) hits for one query, in rank order.

    Rank order is this leg's entire contract — see `dense_search`'s docstring
    for why callers must not re-sort by `score`.
    """
    store = get_vector_store(collection_name, mode=RetrievalMode.SPARSE)
    try:
        hits = store.similarity_search_with_score(query, k=k, filter=query_filter)
    except Exception:
        logger.exception(
            "Sparse search failed on '%s' for query %r", collection_name, query
        )
        raise
    return [to_chunk(document, score, corpus) for document, score in hits]
