from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Single source of truth for all environment configuration.

    Required fields (no default) fail fast at startup if missing from .env,
    rather than surfacing as a confusing error on the first request that needs them.
    """

    model_config = SettingsConfigDict(
        env_file=".env", env_file_encoding="utf-8", extra="ignore"
    )

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
    qdrant_collection: str = "complaint_kb_v1"

    # --- Supabase ---
    supabase_url: str
    supabase_publishable_key: str
    supabase_secret_key: str

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


@lru_cache
def get_settings() -> Settings:
    return Settings()
