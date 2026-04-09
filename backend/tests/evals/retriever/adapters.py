"""Each retriever, reduced to `query -> retrieved chunk texts in rank order`.

The knowledge base is two Qdrant collections, so even a single leg is two
searches with separate quotas (6 cases, 4 policies). `_leg` is that pair, and
is exactly what `cli/retrieve.py::_run_single_leg` does minus the printing.

Rank order is preserved because ContextualPrecision scores *ranking*, not just
membership, and all three functions return the same 10-chunk budget so their
scores can be compared against each other.
"""

import logging
from collections.abc import Callable

from cms.config.settings import get_settings
from cms.retrieval.retrievers.base import RetrievedChunk
from cms.retrieval.retrievers.dense_retriever import dense_search
from cms.retrieval.retrievers.hybrid_retriever import (
    DEFAULT_K_CASES,
    DEFAULT_K_POLICIES,
    build_filter,
    retrieve,
)
from cms.retrieval.retrievers.sparse_retriever import sparse_search

logger = logging.getLogger(__name__)

SearchFn = Callable[..., list[RetrievedChunk]]


def _leg(search: SearchFn, query: str) -> list[str]:
    """One leg over both collections, cases first — the hybrid result's order."""
    settings = get_settings()
    chunks: list[RetrievedChunk] = []
    for collection, corpus, k, published_only in (
        (settings.qdrant_cases_collection, "case", DEFAULT_K_CASES, False),
        (settings.qdrant_policies_collection, "policy", DEFAULT_K_POLICIES, True),
    ):
        chunks += search(
            collection,
            query,
            corpus,
            k,
            build_filter(None, published_only=published_only),
        )
    return [chunk.text for chunk in chunks]


def dense_context(query: str) -> list[str]:
    """Semantic leg only: OpenAI embeddings, cosine ranking."""
    try:
        return _leg(dense_search, query)
    except Exception:
        # Re-raised rather than degraded to []: an empty context scores as a
        # bad retriever, hiding what is really a Qdrant/OpenAI failure.
        logger.exception("Dense retrieval failed for %r", query)
        raise


def sparse_context(query: str) -> list[str]:
    """Lexical leg only: local BM25, exact-term ranking."""
    try:
        return _leg(sparse_search, query)
    except Exception:
        logger.exception("Sparse retrieval failed for %r", query)
        raise


def hybrid_context(query: str) -> list[str]:
    """What production uses: both legs, both collections, fused by RRF."""
    try:
        return [chunk.text for chunk in retrieve(query).chunks]
    except Exception:
        logger.exception("Hybrid retrieval failed for %r", query)
        raise
