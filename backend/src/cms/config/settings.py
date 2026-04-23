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

    # `env_file` is supplied per-instantiation by `get_settings()` rather than
    # pinned here, so the lookup happens when settings are first read instead of
    # when this module is imported — the two differ if the caller chdirs in
    # between, which the notebook does.
    model_config = SettingsConfigDict(env_file_encoding="utf-8", extra="ignore")

    # --- OpenAI ---
    openai_api_key: str
    openai_model_main: str = "gpt-5.4-mini"
    openai_model_cheap: str = "gpt-5.4-nano"

    # --- Embeddings ---
    embedding_model: str = "text-embedding-3-small"
    embedding_dims: int = 1536

    # --- Chunking ---
    # Overlap exists so a clause straddling a chunk boundary is still fully
    # present in at least one chunk. Env-tunable for retrieval experiments;
    # changing either re-ingests the policy corpus via `policy_recipe` below.
    policy_chunk_tokens: int = 800
    policy_chunk_overlap: int = 100

    # --- Ingest recipes ---
    # The short-circuit key covers the source text *and* how we process it, so a
    # strategy change re-ingests instead of silently skipping. Per corpus, so a
    # policy chunking change does not re-embed the cases.
    @property
    def case_recipe(self) -> str:
        """Ingest-key recipe for cases. Bump v1 when `build_case_text` changes."""
        return f"case-v1|{self.embedding_model}"

    @property
    def policy_recipe(self) -> str:
        """Ingest-key recipe for policies. Bump v1 when POLICY_HEADERS or the
        breadcrumb format changes — those are not captured by the numbers."""
        return (
            f"policy-v1|{self.policy_chunk_tokens}-{self.policy_chunk_overlap}"
            f"|{self.embedding_model}"
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
    # Deployments set this. It is empty by default because a wrong guess here
    # fails in the browser rather than at startup, and a default that "almost
    # works" in production is worse than an obvious blank.
    cors_origins: str = ""

    # Local development is matched by pattern instead of by list. Vite does not
    # own a fixed port — it walks 5173, 5174, 5175… whenever the previous one is
    # still held by an earlier `npm run dev`, and `localhost` and `127.0.0.1` are
    # distinct origins to a browser even though they reach the same process. An
    # explicit list therefore breaks silently the moment either changes: plain
    # GETs are simple requests, so the server still logs 200 while the browser
    # discards every response for a missing `Access-Control-Allow-Origin`, and
    # the panels read "Could not reach the API" against a healthy backend.
    #
    # Scoped to loopback http only. It widens nothing a deployment cares about:
    # a remote page cannot forge `Origin`, so matching here still requires a
    # page actually served from the developer's own machine. Set
    # `CORS_ORIGIN_REGEX=` (empty) in production to switch it off entirely.
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
    # The corpus is fixture data that ships outside the package (backend/data/ is
    # git-ignored), so a deployment that wants to re-seed points at wherever it
    # mounted the files. Left unset, `cms.ingestion.seed` finds the source-tree
    # copy — see `resolve_seed_dir` there for the full order.
    seed_data_dir: Path | None = None


@lru_cache
def get_settings() -> Settings:
    """The process-wide Settings, built once.

    `_env_file` is passed per-call rather than pinned in `model_config` so the
    file lookup reflects the working directory at first use. Environment
    variables still take precedence over anything in the file.
    """
    return Settings(_env_file=resolve_env_file())
