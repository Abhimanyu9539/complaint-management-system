"""The API server: Supabase and auth, CORS, logging and metrics, health checks."""

from typing import Literal

from pydantic import BaseModel


class ServerSettings(BaseModel):
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

    # --- Logging and metrics ---
    log_level: str = "INFO"
    # "json" for one JSON object per line; "text" is easier to read in a terminal.
    log_format: Literal["json", "text"] = "json"
    # A caller's own id is kept only if it matches the pattern, so it cannot inject into the log.
    request_id_header: str = "X-Request-ID"
    request_id_pattern: str = r"^[A-Za-z0-9._-]{1,64}$"
    # Polled every few seconds by probes and Prometheus; an access line for each would bury the rest.
    access_log_skip_paths: list[str] = ["/health/live", "/health/ready", "/metrics"]
    # Seconds. A ticket-graph run takes about 5-30s.
    graph_latency_buckets: list[float] = [1, 2, 5, 10, 20, 30, 60, 120]

    # --- Startup and health checks ---
    # Loads spaCy (the Presidio guards) and BM25 before the port opens; a failure stops startup.
    # Off, they load on the first request that needs them — set it off for a fast `--reload`.
    warm_up_on_startup: bool = True
    # Cap on each dependency check. A load balancer's probe usually gives up at about 5s.
    health_check_timeout_seconds: float = 3.0
    # What `/health/ready` checks; any of them down is a 503. Mongo, OpenRouter and SMTP are
    # left to the admin panel: their outages hit every instance alike, so failing readiness
    # for them would only take the whole app out of the load balancer.
    health_ready_dependencies: list[Literal["supabase", "qdrant", "mongo", "openrouter", "smtp"]] = [
        "supabase",
        "qdrant",
    ]

    # --- Agent activity (admin) ---
    # Row cap on the read behind the activity summary; a window above it is truncated and logged.
    agent_runs_summary_max_rows: int = 5000
