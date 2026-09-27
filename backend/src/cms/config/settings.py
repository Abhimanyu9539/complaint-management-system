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
    openai_model_main: str = "gpt-6-luna"
    openai_model_cheap: str = "gpt-6-luna"

    # --- OpenRouter ---
    openrouter_model_main: str = "openai/gpt-6-luna"
    openrouter_model_cheap: str = "openai/gpt-6-luna"
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
    # v2 takes the subject and body as one masked text; v1 took them separately.
    classify_ticket_prompt_version: str = "v2"
    # Intake §7: a top department at or above this routes directly; below goes to human review.
    routing_confidence_floor: float = 0.60
    # The ticket graph's reply written to the customer (the chat's `generate` writes to the agent).
    # v3 adds a department's answer from a similar past case; v2 the ticket's own answer.
    customer_reply_prompt_version: str = "v3"
    # The question emailed to a department when a ticket is escalated.
    dept_question_prompt_version: str = "v1"
    # Title of a department's answer when it is offered to the drafter as a source.
    guidance_title_template: str = "Department guidance — {department}"
    # Kill switch: off, a past case's department answer is only precedent, never a source.
    precedents_enabled: bool = True
    # Reranker score a past case needs before its department answer is offered as a source.
    # Stricter than `policy_relevance_threshold`; tune it from the `ticket-precedents` eval's logged scores.
    precedent_relevance_threshold: float = 0.70
    # `{case}` is the case title, e.g. "T-14 — product_safety / safety".
    precedent_title_template: str = "Earlier department guidance ({case})"
    # The ticket draft when no policy matches. No model call, so no claim to check.
    holding_reply_message: str = (
        "Dear customer,\n\n"
        "Thank you for contacting us. We have received your complaint (reference "
        "T-{ticket_no}) and a specialist is looking into it. We will come back to you "
        "with next steps as soon as we can.\n\n"
        "Kind regards,\nCustomer Care"
    )
    # Stored as `drafts.model` / `drafts.prompt_version` for a holding reply; both columns are NOT NULL.
    holding_reply_model: str = "template"
    holding_reply_prompt_version: str = "holding_reply"

    # --- Email (the reply to the customer) ---
    # Defaults point at Mailpit from docker-compose: it catches every message and delivers none.
    smtp_host: str = "localhost"
    smtp_port: int = 1025
    smtp_username: str | None = None
    smtp_password: str | None = None
    smtp_starttls: bool = False
    smtp_timeout_seconds: float = 10.0
    support_email_from: str = "Customer Care <support@example.com>"
    support_reply_to: str = "support@example.com"
    # The [T-n] tag matches an incoming reply to its ticket (`ticket_ref_pattern`).
    reply_subject_template: str = "Re: {subject} [T-{ticket_no}]"
    # The escalation email to a department. Its reply comes back to `support_reply_to`.
    dept_question_subject_template: str = "[T-{ticket_no}] Question from Customer Care: {subject}"
    dept_question_body_template: str = (
        "{question}\n\n"
        "---\n"
        "Complaint T-{ticket_no}: {subject}\n\n"
        "{body}\n\n"
        "Please reply to this email and keep [T-{ticket_no}] in the subject."
    )
    # Off, only a local SMTP server (Mailpit) is allowed. Sending needs a signed-in
    # agent, but a dev machine should still opt in before mail reaches real people.
    email_real_delivery_enabled: bool = False
    local_smtp_hosts: list[str] = ["localhost", "127.0.0.1", "mailpit"]

    # --- Incoming email (n8n posts each message to /api/v1/emails/inbound) ---
    # The shared secret n8n sends as `X-Inbound-Secret`. Unset turns inbound email off (503).
    inbound_email_secret: str | None = None
    # The ticket reference in a reply's subject; outgoing subjects carry it.
    ticket_ref_pattern: str = r"\[T-(\d+)\]"
    email_subject_fallback: str = "(no subject)"
    email_ticket_severity: str = "normal"
    # Same bounds as `CreateTicketRequest`.
    email_subject_max_chars: int = 200
    email_body_max_chars: int = 8000
    # Lines where quoted history starts in a reply; only the text above the first one is kept.
    reply_quote_markers: list[str] = [
        r"^On .+ wrote:$",
        r"^>",
        r"^-----Original Message-----",
        r"^From: ",
    ]
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
    # Fits `CreateTicketRequest`: the ticket graph guards subject (200) + body (8000) as one text.
    query_min_chars: int = 1
    query_max_chars: int = 8300
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
    # The same feedback for a ticket's customer reply, whose rails check the opposite audience.
    customer_rail_feedback: dict[str, str] = {
        "self check facts": (
            "A reviewer found claims the extracts do not support. Tell the customer only "
            "what the extracts say, and cite each claim."
        ),
        "self check output": (
            "The reply is not fit to send to the customer. Write to the customer, never "
            "mention past cases, other customers or internal scores, and do not blame them."
        ),
    }
    # Model for NeMo's output rails (fact check, tone). Measured on the 30 eval goldens
    # with the material-claims prompt: gpt-5.4-nano blocked 2 of 5 invented remedies,
    # gpt-5.4-mini blocked 5 of 5 with 5/30 drafts caveated. gpt-6-luna is not measured
    # yet. The input rail stays on `openrouter_model_cheap`.
    guard_judge_model: str = "openai/gpt-6-luna"
    # When NeMo's fact check blocks, a cheap model names the unsupported claims.
    fact_check_prompt_version: str = "v1"
    # Enough to act on; more turns the retry feedback into a second draft.
    fact_check_max_claims: int = 5

    # --- Flywheel (a sent reply becomes a past case) ---
    # Kill switch: off, sending a reply mints no case.
    flywheel_enabled: bool = True
    # The internal summary of what was sent, stored as the case's resolution.
    case_resolution_prompt_version: str = "v1"
    # Mirrors the seed `case_title`, with the ticket in place of the case id.
    flywheel_case_title_template: str = "T-{ticket_no} — {department} / {category}"
    # The ticket's own identifiers, replaced before Presidio runs (privacy §6).
    case_entity_masks: dict[str, str] = {"order_no": "<ORDER_NO>", "invoice_no": "<INVOICE_NO>"}

    # --- Agent activity (admin) ---
    # Row cap on the read behind the activity summary; a window above it is truncated and logged.
    agent_runs_summary_max_rows: int = 5000

    @property
    def case_pii_entities(self) -> list[str]:
        """What is masked out of a case before indexing: the input guard's entities plus names."""
        return [*self.pii_entities, "PERSON"]

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

    # --- Auth (Supabase user JWTs, verified against the project's public keys) ---
    supabase_jwt_audience: str = "authenticated"
    supabase_jwt_algorithms: list[str] = ["ES256", "RS256"]
    # Clock difference tolerated on `iat`/`exp`. This machine runs a second or two behind
    # Supabase, which made a token used right after sign-in look issued in the future.
    supabase_jwt_leeway_seconds: int = 30
    # How long the fetched signing keys are reused before the key set is read again.
    jwks_cache_seconds: int = 3600
    jwks_timeout_seconds: float = 10.0

    @property
    def supabase_jwks_url(self) -> str:
        return f"{self.supabase_url}/auth/v1/.well-known/jwks.json"

    @property
    def supabase_jwt_issuer(self) -> str:
        # Stripped: a trailing slash in SUPABASE_URL would fail every token's `iss` check.
        return f"{self.supabase_url.rstrip('/')}/auth/v1"

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
