"""Bootstrap for the eval suite: stdout encoding, truststore, the judge's API key."""

import logging
import os
import sys

import cms.config  # noqa: F401 — truststore injection; must precede any HTTPS client
from cms.config.logging_config import setup_logging
from cms.config.settings import get_settings

logger = logging.getLogger("cms.evals")

# deepeval's judge builds its own OpenAI client and reads OPENAI_API_KEY from
# os.environ, but pydantic-settings parses .env without exporting it. Both fixes
# already exist in the codebase; this only runs them at collection time, before
# any metric is built. `setdefault` rather than assignment: an operator who
# exported a different key for one run means it.
try:
    # The report echoes retrieved policy text (₹, §, em dashes) through rich, and
    # Windows terminals default stdout to cp1252 — which raises rather than
    # mangles. Same fix as cli/retrieve.py.
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")

    setup_logging()
    os.environ.setdefault("OPENAI_API_KEY", get_settings().openai_api_key)
    os.environ.setdefault("DEEPEVAL_TELEMETRY_OPT_OUT", "YES")
except Exception:
    # Never block collection — real environment variables may already be in play.
    logger.exception("Eval bootstrap failed; relying on the process environment")
