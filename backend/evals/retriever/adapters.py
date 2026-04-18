"""Each policy retrieval leg, reduced to `query -> retrieved chunk texts in rank order`.

`asyncio.run` per call is safe here even though cli/retrieve.py warns "exactly one
per process": that warning is about the cached *async* Qdrant and Supabase clients,
which bind pools to their creating loop. This path never touches them — the policy
store wraps the sync QdrantClient and offloads to a thread.
"""

import asyncio
from collections.abc import Awaitable, Callable

from langchain_core.documents import Document

from cms.retrieval.policy_retriever import (
    DEFAULT_K,
    retrieve_policies_dense,
    retrieve_policies_hybrid,
    retrieve_policies_sparse,
)

Retriever = Callable[..., Awaitable[list[tuple[Document, float]]]]


def _context(retrieve: Retriever, query: str) -> list[str]:
    """Rank order is preserved — ContextualPrecision scores ranking, not membership.

    Deliberately unguarded: a Qdrant or OpenAI failure must error the run loudly
    rather than come back as an empty context, which scores as a bad retriever.
    """
    hits = asyncio.run(retrieve(query, k=DEFAULT_K))
    return [document.page_content for document, _ in hits]


def dense_policy_context(query: str) -> list[str]:
    """Semantic leg: cosine over OpenAI embeddings."""
    return _context(retrieve_policies_dense, query)


def sparse_policy_context(query: str) -> list[str]:
    """Lexical leg: BM25 via local fastembed."""
    return _context(retrieve_policies_sparse, query)


def hybrid_policy_context(query: str) -> list[str]:
    """Production path: both legs, fused server-side by Qdrant (RRF)."""
    return _context(retrieve_policies_hybrid, query)
