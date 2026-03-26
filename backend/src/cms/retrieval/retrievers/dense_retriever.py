"""The semantic retrieval leg: dense (`text-embedding-3-small`, cosine) search.

Dense embeddings find paraphrases and synonyms with no shared vocabulary — "my
blender is smoking" retrieving a case about motor overheating. What they blur
is exactly what complaint text is full of: order numbers, error codes, model
names (build.md §0.4). That gap is why the sparse leg in `sparse_retriever.py`
exists; `hybrid_retriever` fuses the two rather than picking one.

Cost: one OpenAI embedding call per query, via the cached `get_dense_embeddings`
client (through `qdrant_store.get_vector_store`, so nothing here talks to
OpenAI directly).
"""

import logging

from langchain_qdrant import RetrievalMode
from qdrant_client import models

from cms.retrieval.retrievers.base import Corpus, RetrievedChunk, to_chunk
from cms.retrieval.vector_store.qdrant_store import get_vector_store

logger = logging.getLogger(__name__)


def dense_search(
    collection_name: str,
    query: str,
    corpus: Corpus,
    k: int,
    query_filter: models.Filter | None,
) -> list[RetrievedChunk]:
    """Top-`k` dense hits for one query, in rank order.

    Rank order is this leg's entire contract: `hybrid_retriever.rrf_fuse`
    consumes positions, not the raw cosine scores, so callers must not re-sort
    the result.
    """
    store = get_vector_store(collection_name, mode=RetrievalMode.DENSE)
    try:
        hits = store.similarity_search_with_score(query, k=k, filter=query_filter)
    except Exception:
        logger.exception(
            "Dense search failed on '%s' for query %r", collection_name, query
        )
        raise
    return [to_chunk(document, score, corpus) for document, score in hits]
