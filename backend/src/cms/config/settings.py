import logging
import os
from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

logger = logging.getLogger(__name__)

ENV_FILE_VAR = "CMS_ENV_FILE"


def resolve_env_file() -> Path | None:
    """Locate the `.env` file without depending on the working directory.

    The package is installed, so entrypoints can be launched from anywhere —
    a relative `".env"` would silently resolve to nothing and the required
    fields below would fail with a confusing "field required" instead of
    "your config wasn't found". Tried in order:

    1. `$CMS_ENV_FILE`, an explicit override for containers and CI.
    2. A `.env` in the cwd or any parent — covers `backend/` and any
       subdirectory of it, which is how this is run in development.
    3. The source-tree `backend/.env`, relative to this file. Only resolves
       for an editable install; a wheel in site-packages has no such parent,
       which is correct — deployments pass real environment variables.

    Returning None is not an error: real env vars still populate Settings, and
    that is the expected path in a deployed container.
    """
    override = os.environ.get(ENV_FILE_VAR)
    if override:
        path = Path(override).expanduser()
        if path.is_file():
            return path
        # Explicitly asked for and not there — worth a warning rather than a
        # silent fallback that loads a *different* file than the one requested.
        logger.warning("%s=%s does not exist; ignoring it", ENV_FILE_VAR, override)

    try:
        cwd = Path.cwd().resolve()
        for directory in (cwd, *cwd.parents):
            candidate = directory / ".env"
            if candidate.is_file():
                return candidate
    except OSError:
        # A deleted or unreadable cwd must not stop us reaching the fallback.
        logger.exception("Could not search upward from the working directory")

    # src/cms/config/settings.py -> backend/
    source_tree = Path(__file__).resolve().parents[3] / ".env"
    if source_tree.is_file():
        return source_tree

    logger.info("No .env file found; relying on process environment variables")
    return None


class Settings(BaseSettings):
    """Single source of truth for all environment configuration.

    Required fields (no default) fail fast at startup if missing, rather than
    surfacing as a confusing error on the first request that needs them.
    """

    model_config = SettingsConfigDict(env_file_encoding="utf-8", extra="ignore")

    # --- OpenAI ---
    openai_api_key: str
    openai_model_main: str = "deepseek/deepseek-v4-pro-0813"
    openai_model_cheap: str = "gpt-5.4-nano"

    # --- OpenRouter ---
    openrouter_model_main: str = "openai/gpt-5.4-mini"
    openrouter_model_cheap: str = "openai/gpt-5.4-nano"
    openrouter_embedding_model: str = "openai/text-embedding-3-small"
    open_router_api_key: str
    openrouter_base_url: str = "https://openrouter.ai/api/v1"
    openrouter_rerank_model: str = "voyageai/rerank-2.5-lite"
    openrouter_timeout_seconds: float = 30.0


    # --- Embeddings ---
    embedding_model: str = "text-embedding-3-small"
    embedding_dims: int = 1536

    # --- Chunking ---
    policy_chunk_tokens: int = 800
    policy_chunk_overlap: int = 100

    # --- Retrieval ---
    case_top_k: int = 4
    policy_top_k: int = 20

    # --- Voyage reranking (policies) ---
    voyage_api_key: str | None = None
    rerank_enabled: bool = True
    rerank_model: str = "rerank-2.5-lite"
    policy_rerank_top_n: int = 12

    # --- Generation ---
    # A guard, not a shaper: 12 reranked chunks measure at ~2,400 tokens, so this
    # only trips if policy_rerank_top_n is raised or a chunk arrives oversized.
    generation_context_tokens: int = 4000
    # How much of a chunk a citation carries for the UI's sources panel. Long
    # enough to judge the match, short enough not to resend the context block.
    citation_snippet_chars: int = 300
    # v4 revises the failed draft on a retry; v3 (feedback only), v2 (no feedback)
    # and v1 (policies only) are kept as the record and eval baselines.
    generate_prompt_version: str = "v4"
    # v3 adds the knowledge_lookup intent and its lookup_target; v2 adds risk flags.
    analyze_query_prompt_version: str = "v3"
    # v2 mentions policy and case lookups in the "what can you do?" answer.
    smalltalk_prompt_version: str = "v2"
    # Ticket triage: department candidates, suggested severity, category, entities.
    classify_ticket_prompt_version: str = "v1"
    # Intake §7: a top department at or above this routes directly; below goes to human review.
    routing_confidence_floor: float = 0.60
    # What we say when retrieval found nothing. Kept here rather than inline in
    # the node so the wording is tunable without a deploy.
    no_match_message: str = (
        "I couldn't find a policy section that covers this complaint, so I have "
        "nothing to base a response on. Please check the policy library directly "
        "or escalate to the responsible department — I'd rather say this than "
        "guess at an entitlement the customer may not have."
    )

    # --- Knowledge lookup (the agent's own policy and case questions) ---
    lookup_prompt_version: str = "v1"
    # Cases fetched by hybrid search before the rerank. The seed corpus is 20 cases.
    lookup_case_pool_k: int = 20
    # Cases kept after the rerank — enough to list, few enough to read.
    lookup_case_top_n: int = 8
    # No case match when the best reranked case scores below this. Same kind of
    # gate as `policy_relevance_threshold`; unmeasured, tune it with cms-graph probes.
    lookup_case_relevance_threshold: float = 0.50
    lookup_no_match_message: str = (
        "I couldn't find a policy or past case that answers this. Try rewording the "
        "question, or check the policy library directly."
    )

    # --- Guardrails ---
    # Kill switches. The Guardrails AI checks run locally; the NeMo rails are LLM calls.
    guardrails_enabled: bool = True
    nemo_rails_enabled: bool = False
    # Same bounds as `CreateTicketRequest.body`.
    query_min_chars: int = 1
    query_max_chars: int = 8000
    # Presidio entities masked out of the complaint and flagged in drafts (privacy §2).
    pii_entities: list[str] = [
        "CREDIT_CARD",
        "IN_AADHAAR",
        "IN_PAN",
        "EMAIL_ADDRESS",
        "PHONE_NUMBER",
    ]
    # Credentials Presidio has no recognizer for: an OTP, UPI PIN or CVV and its digits.
    credential_pattern: str = r"(?i)\b(?:otp|one[- ]time password|upi pin|cvv)\b\D{0,15}\d{3,8}\b"
    # No match when the best reranked policy chunk scores below this (lld.md
    # NO_MATCH_THRESHOLD). Reranked hits only — RRF scores are on another scale.
    # 0.50 measured on the 30 eval goldens: lowest golden best score 0.539;
    # clearly off-topic complaints topped out at 0.47-0.50.
    policy_relevance_threshold: float = 0.50
    blocked_input_message: str = (
        "This complaint was not processed: it contains instructions aimed at the "
        "assistant, abusive content, or text the checks could not accept. Please "
        "read it and handle it manually."
    )
    # Worded for both branches: a complaint draft gets here after one retry, a
    # lookup answer on its first failure.
    grounding_caveat: str = (
        "CAUTION — this answer failed the guardrail checks. Verify every claim "
        "against the cited sources before using any of it:"
    )
    # Recorded when a guard itself errors; the flow fails closed.
    guard_error_reason: str = "A guardrail check could not run."
    # Feedback when Presidio finds personal data in a draft.
    draft_pii_reason: str = (
        "The draft contains personal data (a card, ID, email or phone number). Remove it."
    )
    # Feedback for the regenerated draft, keyed by the NeMo rail that blocked it.
    rail_feedback: dict[str, str] = {
        "self check input": "The complaint contains instructions aimed at the assistant, or abuse.",
        "self check facts": (
            "A reviewer found claims the extracts do not support. State only what the "
            "extracts and past cases say, and cite each claim."
        ),
        "self check output": (
            "The draft is not written to the support agent. Write to the agent, with no "
            "greeting or sign-off, and in a neutral tone about the customer."
        ),
    }
    # Model for NeMo's output rails (fact check, tone). Measured on the 30 eval goldens
    # with the material-claims prompt: gpt-5.4-nano blocked 2 of 5 invented remedies,
    # gpt-5.4-mini blocked 5 of 5 with 5/30 drafts caveated. The input rail stays on
    # `openrouter_model_cheap`.
    guard_judge_model: str = "openai/gpt-5.4-mini"
    # When NeMo's fact check blocks, a cheap model names the unsupported claims.
    fact_check_prompt_version: str = "v1"
    # Enough to act on; more turns the retry feedback into a second draft.
    fact_check_max_claims: int = 5

    # --- Chat ---
    # Sent as the SSE `error` event when the graph raises mid-stream. The real
    # cause is logged; the browser gets something a user can act on.
    chat_error_message: str = (
        "The assistant could not finish this answer. Please try again."
    )

    # --- Mongo / chat memory ---
    # Mongo backs the LangGraph checkpointer, which is where a conversation is
    # stored. Supabase cannot hold it yet: `chat_sessions` and `messages` are
    # RLS'd to `auth.uid()` and this API holds the service-role key. Mongo has
    # no RLS, so the transcript lands here until auth arrives.
    # 27018 is the compose file's host port — see the note there about a native
    # mongod shadowing 27017.
    mongo_url: str = "mongodb://localhost:27018"
    mongo_db_name: str = "cms_chat"
    # Caps how long a down Mongo stalls a request. pymongo's own default is 30s,
    # which is long enough to look like a hang.
    mongo_timeout_ms: int = 5000
    # Kill switch: False compiles the graph with no checkpointer, which is the
    # pre-Mongo behaviour — chat works, nothing is stored.
    chat_memory_enabled: bool = True
    # Stands in for the authenticated user until JWT verification lands. It is
    # recorded in checkpoint metadata, never used to authorise anything.
    anonymous_user_id: str = "anonymous"
    # `input_guard` only masks PII on the *allowed* path; a blocked message is
    # still raw, and blocked is exactly when it holds a credential. Stored in its
    # place so a replayed transcript never shows what was rejected.
    blocked_message_placeholder: str = "[message withheld]"

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

    # --- LangSmith tracing  ---
    langsmith_tracing: bool = True
    langsmith_endpoint: str = "https://api.smith.langchain.com"
    langsmith_api_key: str
    langsmith_project: str = "complaint-cms"

    # --- Qdrant ---
    qdrant_url: str
    qdrant_api_key: str | None = None
    qdrant_cases_collection: str = "cases_v1"
    qdrant_policies_collection: str = "policies_v1"

    # --- Supabase ---
    supabase_url: str
    supabase_publishable_key: str
    supabase_secret_key: str
    # Private bucket policy files upload into; created by migration 0018.
    supabase_policy_bucket: str = "policy-files"

    @property
    def supabase_jwks_url(self) -> str:
        return f"{self.supabase_url}/auth/v1/.well-known/jwks.json"

    # --- CORS: comma-separated origins, e.g. "https://cms.example.com,https://admin.example.com" ---
    cors_origins: str = ""
    cors_origin_regex: str | None = r"http://(localhost|127\.0\.0\.1)(:\d+)?"

    @property
    def cors_origins_list(self) -> list[str]:
        return [
            origin.strip() for origin in self.cors_origins.split(",") if origin.strip()
        ]

    @property
    def cors_origin_regex_or_none(self) -> str | None:
        """The regex, with an env-supplied empty string normalised to None.

        Starlette treats `""` as a pattern that matches every origin's empty
        prefix — i.e. allow-all — so an operator disabling this with
        `CORS_ORIGIN_REGEX=` would get the exact opposite of what they asked
        for. Collapsing blank to None makes the off switch mean off.
        """
        if self.cors_origin_regex is None or not self.cors_origin_regex.strip():
            return None
        return self.cors_origin_regex.strip()

    # --- Seed corpus ---
    seed_data_dir: Path | None = None


@lru_cache
def get_settings() -> Settings:
    """The process-wide Settings, built once.

    `_env_file` is passed per-call rather than pinned in `model_config` so the
    file lookup reflects the working directory at first use. Environment
    variables still take precedence over anything in the file.
    """
    return Settings(_env_file=resolve_env_file())
