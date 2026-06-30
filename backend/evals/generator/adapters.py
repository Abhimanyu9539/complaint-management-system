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

from langchain_core.documents import Document

from cms.rag.context import build_generation_context
from cms.rag.nodes.analyze_query import analyze_query_core, build_policy_queries
from cms.rag.nodes.generate import generate_core
from cms.rag.nodes.retrieve_policies import retrieve_policies_core
from cms.rag.ticket_graph import get_ticket_graph
from cms.rag.ticket_state import drafting_sources, needs_holding_reply
from cms.retrieval.retrievers.case_retriever import retrieve_cases_hybrid
from cms.retrieval.retrievers.policy_retriever import DEFAULT_TOP_N as POLICY_TOP_N

logger = logging.getLogger(__name__)

# Goldens in flight at once. Each is a fan-out of several embedding and Qdrant
# calls plus a generation, so this is not the place to be greedy.
CONCURRENT_GOLDENS = 5

# (retrieval_context, draft) for one golden.
GenerationCase = tuple[list[str], str]

# How the ticket graph's guard treated each draft, one entry per golden. aggregate.py prints the totals.
GATE_OUTCOMES: list[dict] = []


def offered_contexts(
    sources: list[tuple[Document, float]], case_hits: list[tuple[Document, float]]
) -> list[str]:
    """The chunk texts the drafter was shown, sources then cases, cut where the token budget cut them."""
    _, _, offered = build_generation_context(sources, case_hits)
    offered_cases = sum(1 for citation in offered if citation.doc_type == "case")
    offered_sources = len(offered) - offered_cases
    contexts = [document.page_content for document, _ in sources[:offered_sources]]
    contexts += [document.page_content for document, _ in case_hits[:offered_cases]]
    return contexts


async def graph_generation_case(query: str) -> GenerationCase:
    """The production path end to end: analyze, retrieve policies and cases, rerank, generate.

    `retrieval_context` is what the model was actually shown, not the raw hits:
    `build_context` stops at the token budget, so a hit past the cut never
    reached the model and must not be counted against faithfulness. Calling
    `build_generation_context` here duplicates the call inside `generate_core`,
    which is free — it is pure, with no I/O.

    Policy texts come first, then case texts — the same order as the markers, so
    `log_citation_health`'s marker range check still lines up.
    """
    analysis = await analyze_query_core(query)
    queries = build_policy_queries(query, analysis)
    policy_hits, case_hits = await asyncio.gather(
        retrieve_policies_core(queries, rerank=True, top_n=POLICY_TOP_N),
        retrieve_cases_hybrid(query),
    )

    _, _, offered = build_generation_context(policy_hits, case_hits)
    offered_policies = sum(1 for citation in offered if citation.doc_type == "policy")
    offered_cases = len(offered) - offered_policies
    draft, cited = await generate_core(query, policy_hits, case_hits)

    logger.info(
        "generation leg | %s",
        "\n".join(
            [
                f"golden:  {query}",
                f"  intent: {analysis.intent}",
                (f"  chunks: {offered_policies} policy + {offered_cases} case offered, "
                f"{len(cited)} cited"),
            ]
        ),
    )
    return offered_contexts(policy_hits, case_hits), draft


async def ticket_graph_case(query: str) -> GenerationCase:
    """The ticket graph end to end: guard, classify, retrieve, draft the customer reply, check it.

    The compiled graph only computes, so nothing is written to the database.
    A holding reply was drafted from nothing, so its context is empty. With no
    department answer on an eval ticket, every guidance citation is an earlier one.
    """
    state = await get_ticket_graph().ainvoke({"ticket_id": "eval", "ticket_no": 0, "query": query})
    outcome = {
        "grounded": state.get("grounded"),
        "regenerated": bool(state.get("regenerated")),
        "holding": needs_holding_reply(state),
        "input_blocked": bool(state.get("input_blocked")),
        "failed": sorted(state.get("errors", {})),
        "precedents": len(state.get("precedent_hits", [])),
        "precedents_cited": sum(1 for c in state.get("citations", []) if c.doc_type == "guidance"),
    }
    GATE_OUTCOMES.append(outcome)
    for stage, error in state.get("errors", {}).items():
        logger.warning("ticket leg | %s failed for %r: %s", stage, query[:60], error)

    draft = state.get("draft") or ""
    contexts: list[str] = []
    if not draft:
        logger.warning("ticket leg | no draft for %r: %s", query[:60], outcome)
    elif not outcome["holding"]:
        contexts = offered_contexts(drafting_sources(state), state.get("case_hits", []))
    logger.info("ticket leg | %r: %s, %d chunk(s) offered", query[:60], outcome, len(contexts))
    return contexts, draft


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
