"""Each retrieval leg, reduced to `query -> retrieved chunk texts in rank order`.

Both corpora, and each keeps its own `DEFAULT_K` — policies at 20, cases at 4 — so
the scores describe what production actually retrieves. That makes the legs
comparable within a corpus, which is the comparison the suite exists for; it does
not make policy and case numbers comparable to each other.

Policies come in pairs: a plain leg on the raw k=20 pool and a `reranked_` leg that
reranks it down to `POLICY_TOP_N`. Both pass `rerank=` explicitly rather than
inheriting `RERANK_ENABLED`, so flipping that env var cannot quietly turn the
baseline into a second copy of the reranked leg and make the comparison meaningless.
`graph_reranked_policy_context` is the odd one out: it is the multi-query graph
path, where breadth comes from the fan-out and one rerank over the union caps it.

`asyncio.run` per call is safe here even though cli/retrieve.py warns "exactly one
per process": that warning is about the cached *async* Qdrant and Supabase clients,
which bind pools to their creating loop. This path never touches them — both stores
wrap the sync QdrantClient and offload to a thread.
"""

import asyncio
import logging
from collections.abc import Awaitable, Callable

from langchain_core.documents import Document

from cms.rag.nodes.analyze_query import analyze_query_core, build_policy_queries
from cms.rag.nodes.retrieve_policies import retrieve_policies_core
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

logger = logging.getLogger(__name__)

Retriever = Callable[..., Awaitable[list[tuple[Document, float]]]]

# Goldens in flight at once on an async leg. Each one is already a fan-out of
# several embedding and Qdrant calls, so this is not the place to be greedy.
CONCURRENT_GOLDENS = 5


def _context(retrieve: Retriever, query: str, k: int, **kwargs) -> list[str]:
    """Rank order is preserved — ContextualPrecision scores ranking, not membership.

    Deliberately unguarded: a Qdrant, OpenAI or OpenRouter failure must error the run
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
    """Dense candidates, reranked down to POLICY_TOP_N."""
    return _context(
        retrieve_policies_dense, query, POLICY_K, rerank=True, top_n=POLICY_TOP_N
    )


def reranked_hybrid_policy_context(query: str) -> list[str]:
    """Production path: hybrid candidates, reranked down to POLICY_TOP_N."""
    return _context(
        retrieve_policies_hybrid, query, POLICY_K, rerank=True, top_n=POLICY_TOP_N
    )


async def graph_reranked_policy_context(query: str) -> list[str]:
    """The graph path: analyze_query's fan-out, merged, reranked to POLICY_TOP_N.
    """
    analysis = await analyze_query_core(query)
    queries = build_policy_queries(query, analysis)
    # One record, not one per query: goldens run CONCURRENT_GOLDENS at a time, and
    # separate log calls interleave into something you cannot attribute. [0] is
    # the golden's own wording, so it is labelled rather than numbered with the
    # rewrites.
    logger.info(
        "graph leg | %s",
        "\n".join(
            [f"golden:  {query}", f"  intent: {analysis.intent}"]
            + [f"  q{i}:     {rewrite}" for i, rewrite in enumerate(queries[1:], 1)]
        ),
    )
    hits = await retrieve_policies_core(queries, rerank=True, top_n=POLICY_TOP_N)
    return [document.page_content for document, _ in hits]


async def _gather_contexts(
    retrieve_context: Callable[[str], Awaitable[list[str]]], queries: list[str]
) -> list[list[str]]:
    limit = asyncio.Semaphore(CONCURRENT_GOLDENS)

    async def one(query: str) -> list[str]:
        async with limit:
            return await retrieve_context(query)

    return list(await asyncio.gather(*(one(query) for query in queries)))


def build_contexts(retrieve_context: Callable, queries: list[str]) -> list[list[str]]:
    """Every golden's retrieval context, in order.

    An async leg runs the whole dataset in one loop. It has to: the embedding
    client is cached for the process and binds its connection pool to the loop
    that created it, so a second `asyncio.run` doing concurrent embeds dies with
    "Event loop is closed". The sync legs embed once per call, never trip it, and
    keep their loop-per-golden.
    """
    if asyncio.iscoroutinefunction(retrieve_context):
        return asyncio.run(_gather_contexts(retrieve_context, queries))
    return [retrieve_context(query) for query in queries]


def dense_case_context(query: str) -> list[str]:
    """Semantic leg: cosine over OpenAI embeddings."""
    return _context(retrieve_cases_dense, query, CASE_K)


def sparse_case_context(query: str) -> list[str]:
    """Lexical leg: BM25 via local fastembed."""
    return _context(retrieve_cases_sparse, query, CASE_K)


def hybrid_case_context(query: str) -> list[str]:
    """Production path: both legs, fused server-side by Qdrant (RRF)."""
    return _context(retrieve_cases_hybrid, query, CASE_K)
