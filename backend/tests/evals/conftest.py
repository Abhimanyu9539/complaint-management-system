"""Process bootstrap for the retriever eval suite.

deepeval's judge builds its own OpenAI client and reads `OPENAI_API_KEY` from
`os.environ`, but pydantic-settings parses `backend/.env` without exporting it —
so without this file the metrics fail on a missing key, and on this machine on
`CERTIFICATE_VERIFY_FAILED` before that (see `cms/config/__init__.py`).

Both fixes already exist; this only runs them at collection time, before the
test modules build any metric.
"""

import logging

# Imported for its side effects: truststore injection. Must precede anything
# that constructs an HTTPS client.
import cms.config  # noqa: F401
from cms.cli.deepeval_launcher import export_env
from cms.config.logging_config import setup_logging

logger = logging.getLogger("cms.tests.evals")

try:
    setup_logging()
    export_env()
except Exception:
    # Never block collection: a missing .env still leaves real environment
    # variables in play, and the metrics report the failure clearly enough.
    logger.exception("Eval bootstrap failed; relying on the process environment")
