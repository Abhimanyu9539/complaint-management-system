"""Bootstrap for the eval suite: stream encoding, truststore, telemetry opt-out."""

import logging
import os
import sys

import cms.config  # noqa: F401 — truststore injection; must precede any HTTPS client
from cms.config.logging_config import setup_logging

logger = logging.getLogger("cms.evals")

# No OPENAI_API_KEY export here any more: metrics.py hands the judge its key and
# base URL explicitly, so nothing reads it off the environment.
try:
    # The report echoes retrieved policy text (₹, §, em dashes) through rich, and
    # Windows terminals default stdout to cp1252 — which raises rather than
    # mangles. Same fix as cli/retrieve.py. stderr too, because that is where
    # `basicConfig` puts its handler and the log lines quote the goldens.
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8", errors="replace")

    setup_logging()
    os.environ.setdefault("DEEPEVAL_TELEMETRY_OPT_OUT", "YES")
except Exception:
    # Never block collection — real environment variables may already be in play.
    logger.exception("Eval bootstrap failed; relying on the process environment")
