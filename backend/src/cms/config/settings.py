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

    # --- Retrieval / routing tunables (env-tunable so eval-driven changes don't need a release) ---
    dept_confidence_threshold: float = 0.60
    max_retrieval_attempts: int = 2

    # --- CORS: comma-separated origins, e.g. "http://localhost:5173,http://localhost:3000" ---
    cors_origins: str = "http://localhost:5173"

    @property
    def cors_origins_list(self) -> list[str]:
        return [
            origin.strip() for origin in self.cors_origins.split(",") if origin.strip()
        ]

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
