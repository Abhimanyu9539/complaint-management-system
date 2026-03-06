"""App package initialization.

Does two things that must happen before anything else imports:

1. Injects the operating system's trust store into Python's ssl module (below).
2. Exports the LangSmith settings into `os.environ`. The LangSmith SDK reads
   its configuration from environment variables only — it never sees our
   `Settings` object — and `pydantic-settings` parses `.env` without exporting
   it. Without this bridge, tracing silently does nothing: `@traceable` never
   raises, it just drops the run on the floor.

Injects the operating system's trust store into Python's ssl module *before*
any HTTPS client (httpx, supabase, openai, qdrant, langsmith) is constructed.

This machine has a TLS-intercepting proxy/AV whose root CA is present in the
Windows certificate store but not in certifi's bundle, so certifi-based
verification fails with "unable to get local issuer certificate". truststore
delegates verification to the OS store, which trusts that root.
"""

import logging

logger = logging.getLogger(__name__)

try:
    import truststore

    truststore.inject_into_ssl()
    logger.info("truststore injected: HTTPS verification now uses the OS trust store")
except Exception:
    # Never let a trust-store setup problem crash import; fall back to certifi.
    logger.exception("Failed to inject truststore; falling back to certifi defaults")


def _export_langsmith_env() -> None:
    """Bridge the LangSmith settings into the env vars its SDK actually reads.

    Existing env vars win: an operator exporting LANGSMITH_* in a shell or CI
    job should be able to override .env without editing the file.
    """
    import os

    from app.config import get_settings

    settings = get_settings()
    for name, value in (
        ("LANGSMITH_TRACING", str(settings.langsmith_tracing).lower()),
        ("LANGSMITH_ENDPOINT", settings.langsmith_endpoint),
        ("LANGSMITH_API_KEY", settings.langsmith_api_key),
        ("LANGSMITH_PROJECT", settings.langsmith_project),
    ):
        os.environ.setdefault(name, value)


try:
    _export_langsmith_env()
    logger.debug("LangSmith environment exported from settings")
except Exception:
    # Tracing is observability, not function — a bad LangSmith config must not
    # stop the app or a script from running.
    logger.exception("Failed to export LangSmith environment; tracing may be disabled")
