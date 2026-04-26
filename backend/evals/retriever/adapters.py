"""Each retrieval leg, reduced to `query -> retrieved chunk texts in rank order`.

Both corpora, and each keeps its own `DEFAULT_K` — policies at 20, cases at 4 — so
the scores describe what production actually retrieves. That makes the legs
comparable within a corpus, which is the comparison the suite exists for; it does
not make policy and case numbers comparable to each other.

Policies come in pairs: a plain leg on the raw k=20 pool and a `reranked_` leg that
Voyage-reranks it down to `POLICY_TOP_N`. Both pass `rerank=` explicitly rather than
inheriting `RERANK_ENABLED`, so flipping that env var cannot quietly turn the
baseline into a second copy of the reranked leg and make the comparison meaningless.

`asyncio.run` per call is safe here even though cli/retrieve.py warns "exactly one
per process": that warning is about the cached *async* Qdrant and Supabase clients,
which bind pools to their creating loop. This path never touches them — both stores
wrap the sync QdrantClient and offload to a thread.
"""

import asyncio
from collections.abc import Awaitable, Callable

from langchain_core.documents import Document

from cms.retrieval.retrievers.case_retriever import (
    DEFAULT_K as CASE_K,
)
from cms.retrieval.retrievers.case_retriever import (
    retrieve_cases_dense,
    retrieve_cases_hybrid,
    retrieve_cases_sparse,
)
from cms.retrieval.retrievers.policy_retriever import (
    DEFAULT_K as POLICY_K,
)
from cms.retrieval.retrievers.policy_retriever import (
    DEFAULT_TOP_N as POLICY_TOP_N,
)
from cms.retrieval.retrievers.policy_retriever import (
    retrieve_policies_dense,
    retrieve_policies_hybrid,
    retrieve_policies_sparse,
)

Retriever = Callable[..., Awaitable[list[tuple[Document, float]]]]


def _context(retrieve: Retriever, query: str, k: int, **kwargs) -> list[str]:
    """Rank order is preserved — ContextualPrecision scores ranking, not membership.

    Deliberately unguarded: a Qdrant, OpenAI or Voyage failure must error the run
    loudly rather than come back as an empty or unreranked context, either of which
    scores as a retriever that is not the one under test.
    """
    hits = asyncio.run(retrieve(query, k=k, **kwargs))
    return [document.page_content for document, _ in hits]


def dense_policy_context(query: str) -> list[str]:
    """Semantic leg: cosine over OpenAI embeddings."""
    return _context(retrieve_policies_dense, query, POLICY_K, rerank=False)


def sparse_policy_context(query: str) -> list[str]:
    """Lexical leg: BM25 via local fastembed."""
    return _context(retrieve_policies_sparse, query, POLICY_K, rerank=False)


def hybrid_policy_context(query: str) -> list[str]:
    """Both legs, fused server-side by Qdrant (RRF). The pre-rerank baseline."""
    return _context(retrieve_policies_hybrid, query, POLICY_K, rerank=False)


def reranked_dense_policy_context(query: str) -> list[str]:
    """Dense candidates, Voyage-reranked down to POLICY_TOP_N."""
    return _context(
        retrieve_policies_dense, query, POLICY_K, rerank=True, top_n=POLICY_TOP_N
    )


def reranked_hybrid_policy_context(query: str) -> list[str]:
    """Production path: hybrid candidates, Voyage-reranked down to POLICY_TOP_N."""
    return _context(
        retrieve_policies_hybrid, query, POLICY_K, rerank=True, top_n=POLICY_TOP_N
    )


def dense_case_context(query: str) -> list[str]:
    """Semantic leg: cosine over OpenAI embeddings."""
    return _context(retrieve_cases_dense, query, CASE_K)


def sparse_case_context(query: str) -> list[str]:
    """Lexical leg: BM25 via local fastembed."""
    return _context(retrieve_cases_sparse, query, CASE_K)


def hybrid_case_context(query: str) -> list[str]:
    """Production path: both legs, fused server-side by Qdrant (RRF)."""
    return _context(retrieve_cases_hybrid, query, CASE_K)
