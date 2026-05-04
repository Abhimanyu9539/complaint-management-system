"""One golden -> what the model was shown and what it wrote.

The generation counterpart to `retriever/adapters.py`. Where that one stops at
`retrieval_context`, this runs the rest of the complaint branch and returns the
draft too, so faithfulness can be scored against the chunks that produced it.

Async throughout, and the whole dataset runs in one event loop — the same
constraint the retriever's graph leg carries. The embedding client is `lru_cache`d
and binds its connection pool to the loop that built it, so a second
`asyncio.run` doing concurrent embeds dies with "Event loop is closed".
"""

import asyncio
import logging
from collections.abc import Awaitable, Callable

from cms.rag.context import build_context
from cms.rag.nodes.analyze_query import analyze_query_core, build_policy_queries
from cms.rag.nodes.generate import generate_core
from cms.rag.nodes.retrieve_policies import retrieve_policies_core
from cms.retrieval.retrievers.policy_retriever import DEFAULT_TOP_N as POLICY_TOP_N

logger = logging.getLogger(__name__)

# Goldens in flight at once. Each is a fan-out of several embedding and Qdrant
# calls plus a generation, so this is not the place to be greedy.
CONCURRENT_GOLDENS = 5

# (retrieval_context, draft) for one golden.
GenerationCase = tuple[list[str], str]


async def graph_generation_case(query: str) -> GenerationCase:
    """The production path end to end: analyze, retrieve, rerank, generate.

    `retrieval_context` is what the model was actually shown, not the raw hits:
    `build_context` stops at the token budget, so a hit past the cut never
    reached the model and must not be counted against faithfulness. Calling
    `build_context` here duplicates the call inside `generate_core`, which is
    free — it is pure, with no I/O.
    """
    analysis = await analyze_query_core(query)
    queries = build_policy_queries(query, analysis)
    hits = await retrieve_policies_core(queries, rerank=True, top_n=POLICY_TOP_N)

    _, offered = build_context(hits)
    draft, cited = await generate_core(query, hits)

    logger.info(
        "generation leg | %s",
        "\n".join(
            [
                f"golden:  {query}",
                f"  intent: {analysis.intent}",
                f"  chunks: {len(offered)} offered, {len(cited)} cited",
            ]
        ),
    )
    return [document.page_content for document, _ in hits[: len(offered)]], draft


async def _gather_cases(
    run_case: Callable[[str], Awaitable[GenerationCase]], queries: list[str]
) -> list[GenerationCase]:
    limit = asyncio.Semaphore(CONCURRENT_GOLDENS)

    async def one(query: str) -> GenerationCase:
        async with limit:
            return await run_case(query)

    return list(await asyncio.gather(*(one(query) for query in queries)))


def build_cases(
    run_case: Callable[[str], Awaitable[GenerationCase]], queries: list[str]
) -> list[GenerationCase]:
    """Every golden's (retrieval_context, draft), in order, in one event loop."""
    return asyncio.run(_gather_cases(run_case, queries))
