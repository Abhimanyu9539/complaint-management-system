"""Export the LangSmith settings into `os.environ`, the only place its SDK reads them.

Without it `@traceable` silently drops every run. Called once from `cms.config`.
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
