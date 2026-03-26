"""Hybrid retrieval: dense + sparse legs, fused by rank, across both corpora.

`QdrantVectorStore` in `RetrievalMode.HYBRID` can already do dense + sparse
prefetch and RRF fusion server-side in a single `query_points` call. This
module deliberately does not use that path. It runs `dense_retriever` and
`sparse_retriever` as two independent legs and fuses them itself, because:

- each leg then has to work standing alone — `--leg dense` / `--leg sparse` in
  the CLI is a debugging question, not a code change;
- the graph's self-correction loop already needs client-side fusion across
  *query variants* (steps.md: "merges by best rank"); doing both axes — legs
  and variants — through one `rrf_fuse` call means one fusion mechanism
  instead of two with different constants.

The cost is more Qdrant round-trips (two per query variant per corpus instead
of one) and re-implementing RRF. No extra OpenAI cost: the dense leg embeds
each query exactly once either way, and the sparse leg is local fastembed.

Cases and policies are separate collections with independently-calibrated
BM25 IDF (see `qdrant_store`'s module docstring), so they are never merged
into one ranked list — each corpus gets its own fixed quota
(`DEFAULT_K_CASES` + `DEFAULT_K_POLICIES` = build.md §0.3.2's "top 10
candidates"), returned as two labelled groups.
"""

import logging

from langsmith import traceable
from pydantic import BaseModel, ConfigDict
from qdrant_client import models

from cms.config.settings import get_settings
from cms.retrieval.retrievers.base import Corpus, RetrievedChunk
from cms.retrieval.retrievers.dense_retriever import dense_search
from cms.retrieval.retrievers.sparse_retriever import sparse_search

logger = logging.getLogger(__name__)

# Standard reciprocal-rank-fusion constant: dampens the influence of very
# high individual ranks so one lucky #1 doesn't dominate a chunk that ranks
# consistently well across legs/variants.
RRF_K = 60

# 6 + 4 = build.md §0.3.2's "top 10 candidates", split so both corpora are
# always represented rather than one corpus crowding the other out.
DEFAULT_K_CASES = 6
DEFAULT_K_POLICIES = 4

# Fetched per leg per query variant, before fusion and truncation to the
# defaults above — wider than the final k so fusion has enough to work with.
FETCH_K = 20

# The only `policies.lifecycle` value retrieval should surface by default;
# `draft`/`in_review`/`retired` clauses are not yet (or no longer) authoritative.
PUBLISHED = "published"


class RetrievalResult(BaseModel):
    """Everything one `retrieve()` call produced, plus what it actually asked for.

    `queries` and `departments` are echoed back rather than left implicit:
    retrieval that silently widened, narrowed, or rewrote its filter is
    otherwise invisible to both the CLI probe and the future `retrieve` node
    that will copy these into `GraphState`.
    """

    model_config = ConfigDict(frozen=True)

    cases: list[RetrievedChunk]
    policies: list[RetrievedChunk]
    queries: list[str]
    departments: list[str] | None

    @property
    def chunks(self) -> list[RetrievedChunk]:
        """Every retrieved chunk, cases first, for callers that want everything."""
        return [*self.cases, *self.policies]


def _normalize_queries(query: str | list[str]) -> list[str]:
    raw = [query] if isinstance(query, str) else list(query)
    seen: set[str] = set()
    normalized: list[str] = []
    for q in raw:
        q = q.strip()
        if q and q not in seen:
            seen.add(q)
            normalized.append(q)
    if not normalized:
        raise ValueError("retrieve() needs at least one non-empty query")
    return normalized


def build_filter(
    departments: list[str] | None, *, published_only: bool = False
) -> models.Filter | None:
    """The payload filter for one corpus query.

    `departments` widens from `MatchValue` (one department) to `MatchAny`
    (several) — this is the low-confidence widening build.md §0.3.2 calls for;
    this function only shapes the filter, the *decision* of how many
    departments to include belongs to the future `retrieve` node.

    `published_only` adds a `metadata.lifecycle` condition and must only be
    passed for the policies collection — `lifecycle` is not indexed (or
    meaningful) on cases, which use `category` instead.

    Returns `None`, not an empty `Filter(must=[])`, when there is nothing to
    filter on — an unfiltered query is what "no departments given" means.
    """
    conditions: list[models.FieldCondition] = []

    if departments:
        match = (
            models.MatchValue(value=departments[0])
            if len(departments) == 1
            else models.MatchAny(any=departments)
        )
        conditions.append(models.FieldCondition(key="metadata.department", match=match))

    if published_only:
        conditions.append(
            models.FieldCondition(
                key="metadata.lifecycle", match=models.MatchValue(value=PUBLISHED)
            )
        )

    if not conditions:
        return None
    return models.Filter(must=conditions)


def rrf_fuse(ranked_lists: list[list[RetrievedChunk]], k: int) -> list[RetrievedChunk]:
    """Reciprocal-rank fusion over any number of ranked lists.

    `score = sum(1 / (RRF_K + rank))` per `point_id`, summed across every list
    it appears in, then sorted descending and truncated to `k`. Used for both
    axes this module needs to merge — legs (dense vs sparse) and query
    variants — because a chunk found consistently by several lists should
    outrank one that is #1 in only one of them, and one function keeps that
    logic (and its constant) in a single place.

    Fusing by rank, not by the lists' raw `score`, is required: those scores
    are a cosine similarity from the dense leg and a BM25 score from the
    sparse leg — never on the same scale (see `base.RetrievedChunk`).
    """
    fused: dict[str, float] = {}
    representative: dict[str, RetrievedChunk] = {}

    for ranked in ranked_lists:
        for rank, chunk in enumerate(ranked):
            fused[chunk.point_id] = fused.get(chunk.point_id, 0.0) + 1.0 / (RRF_K + rank)
            representative.setdefault(chunk.point_id, chunk)

    ordered_ids = sorted(fused, key=lambda pid: fused[pid], reverse=True)
    return [
        representative[pid].model_copy(update={"score": fused[pid]})
        for pid in ordered_ids[:k]
    ]


def _search_corpus(
    collection_name: str,
    corpus: Corpus,
    queries: list[str],
    k: int,
    query_filter: models.Filter | None,
) -> list[RetrievedChunk]:
    """Run both legs for every query variant against one collection, then fuse."""
    ranked_lists: list[list[RetrievedChunk]] = []
    leg_hits = {"dense": 0, "sparse": 0}

    for query in queries:
        dense_hits = dense_search(collection_name, query, corpus, FETCH_K, query_filter)
        sparse_hits = sparse_search(collection_name, query, corpus, FETCH_K, query_filter)
        leg_hits["dense"] += len(dense_hits)
        leg_hits["sparse"] += len(sparse_hits)
        ranked_lists.append(dense_hits)
        ranked_lists.append(sparse_hits)

    # A leg silently returning nothing (wrong vector name, missing IDF) is
    # otherwise invisible behind a plausible-looking fused list — log it.
    logger.info(
        "Retrieved from '%s': dense=%d sparse=%d hits across %d quer(y/ies)",
        collection_name,
        leg_hits["dense"],
        leg_hits["sparse"],
        len(queries),
    )
    return rrf_fuse(ranked_lists, k)


@traceable(name="retrieve")
def retrieve(
    query: str | list[str],
    *,
    departments: list[str] | None = None,
    k_cases: int = DEFAULT_K_CASES,
    k_policies: int = DEFAULT_K_POLICIES,
    published_only: bool = True,
) -> RetrievalResult:
    """Hybrid, department-filtered retrieval over both corpora.

    `query` accepts a single string or the multi-query variants
    `analyze_query` will eventually produce; blank/duplicate variants are
    dropped, and an all-blank input raises `ValueError` rather than silently
    returning nothing.

    Every Qdrant call underneath is allowed to raise (logged first,
    re-raised) rather than degrade — deliberately unlike
    `qdrant_store.collection_stats`, which returns a degraded row for the
    admin dashboard. A dashboard tile can be blank; silently returning half
    the evidence here would let a future `generate` node write a confident,
    ungrounded answer with no signal that a leg or a corpus was never
    consulted — exactly the failure mode this system exists to prevent.
    """
    settings = get_settings()
    queries = _normalize_queries(query)

    cases = _search_corpus(
        settings.qdrant_cases_collection,
        "case",
        queries,
        k_cases,
        build_filter(departments),
    )
    policies = _search_corpus(
        settings.qdrant_policies_collection,
        "policy",
        queries,
        k_policies,
        build_filter(departments, published_only=published_only),
    )

    return RetrievalResult(
        cases=cases, policies=policies, queries=queries, departments=departments
    )
