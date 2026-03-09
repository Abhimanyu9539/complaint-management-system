"""LangSmith setup.

The LangSmith SDK is configured exclusively through environment variables — it
never sees our `Settings` object — while `pydantic-settings` reads `.env`
without exporting anything into `os.environ`. `setup_tracing()` is the bridge
between the two. Skipping it does not raise anywhere: `@traceable` degrades to a
no-op and every run is silently dropped, which is the failure mode this module
exists to prevent.

Called once at import time from `config/__init__.py`, so no entrypoint has to
remember it.
"""

import logging
import os

from cms.config.settings import get_settings

logger = logging.getLogger(__name__)


def setup_tracing() -> None:
    """Export the LangSmith settings into the env vars its SDK actually reads.

    Existing env vars win: an operator exporting LANGSMITH_* in a shell or CI
    job should be able to override .env without editing the file.
    """
    settings = get_settings()

    for name, value in (
        ("LANGSMITH_TRACING", str(settings.langsmith_tracing).lower()),
        ("LANGSMITH_ENDPOINT", settings.langsmith_endpoint),
        ("LANGSMITH_API_KEY", settings.langsmith_api_key),
        ("LANGSMITH_PROJECT", settings.langsmith_project),
    ):
        os.environ.setdefault(name, value)

    logger.debug(
        "LangSmith tracing=%s project=%s",
        os.environ.get("LANGSMITH_TRACING"),
        os.environ.get("LANGSMITH_PROJECT"),
    )
