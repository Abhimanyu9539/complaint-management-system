"""Process bootstrap, run on the first import of any `cms` module.

Injects the OS trust store into `ssl` (for TLS-intercepting antivirus or proxies) and exports the LangSmith
settings to the environment. Neither step may crash the process.
"""

import logging

logger = logging.getLogger(__name__)

try:
    import truststore

    truststore.inject_into_ssl()
    logger.info("truststore injected: HTTPS verification now uses the OS trust store")
except Exception:
    logger.exception("Failed to inject truststore; falling back to certifi defaults")

try:
    # Imported here rather than at the top so a tracing failure cannot take the
    # truststore injection down with it.
    from cms.observability.tracing import setup_tracing

    setup_tracing()
    logger.debug("LangSmith environment exported from settings")
except Exception:
    logger.exception("Failed to export LangSmith environment; tracing may be disabled")
