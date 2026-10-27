"""Embeddings, chunking, search, reranking and the Qdrant collections."""

from pathlib import Path

from pydantic import BaseModel


class RetrievalSettings(BaseModel):
    # --- Embeddings ---
    embedding_model: str = "text-embedding-3-small"
    embedding_dims: int = 1536

    # --- Chunking ---
    policy_chunk_tokens: int = 800
    policy_chunk_overlap: int = 100

    # --- Retrieval ---
    # Cases kept after the rerank in the complaint branch; also the raw retriever legs' default `k`.
    case_top_k: int = 4
    # Cases fetched by hybrid search before the rerank. The seed corpus is 20 cases.
    case_pool_k: int = 20
    # Per-case floor on reranked scores: a case below it never reaches the drafter.
    # Backed by the precedents eval's gap (best wrong case 0.44, intended 0.84+);
    # not yet measured on the 30-case set.
    case_relevance_threshold: float = 0.50
    policy_top_k: int = 20
    # No match when the best reranked policy chunk scores below this.
    # Reranked hits only — RRF scores are on another scale.
    # 0.50 measured on the 30 eval goldens: lowest golden best score 0.539;
    # clearly off-topic complaints topped out at 0.47-0.50.
    policy_relevance_threshold: float = 0.50

    # --- Voyage reranking (policies) ---
    voyage_api_key: str | None = None
    rerank_enabled: bool = True
    rerank_model: str = "rerank-2.5-lite"
    policy_rerank_top_n: int = 12

    # --- Knowledge lookup (the agent's own policy and case questions) ---
    # Cases fetched by hybrid search before the rerank. The seed corpus is 20 cases.
    lookup_case_pool_k: int = 20
    # Cases kept after the rerank — enough to list, few enough to read.
    lookup_case_top_n: int = 8
    # No case match when the best reranked case scores below this. Same kind of
    # gate as `policy_relevance_threshold`; unmeasured, tune it with cms-graph probes.
    lookup_case_relevance_threshold: float = 0.50

    # --- Qdrant ---
    qdrant_url: str
    qdrant_api_key: str | None = None
    qdrant_cases_collection: str = "cases_v1"
    qdrant_policies_collection: str = "policies_v1"

    # --- Seed corpus ---
    seed_data_dir: Path | None = None

    # --- Ingest recipes ---
    # The short-circuit key covers the source text *and* how we process it, so a
    # strategy change re-ingests instead of silently skipping. Per corpus, so a
    # policy chunking change does not re-embed the cases.
    @property
    def case_recipe(self) -> str:
        """Ingest-key recipe for cases. Bump v1 when `build_case_text` changes."""
        return f"case-v1|{self.embedding_model}-{self.embedding_dims}"

    @property
    def policy_recipe(self) -> str:
        """Ingest-key recipe for policies. Bump v1 when POLICY_HEADERS or the
        breadcrumb format changes — those are not captured by the numbers."""
        return (
            f"policy-v1|{self.policy_chunk_tokens}-{self.policy_chunk_overlap}"
            f"|{self.embedding_model}-{self.embedding_dims}"
        )
