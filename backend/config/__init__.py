"""Process bootstrap — runs before anything else in the codebase can misbehave.

Every module in this project reaches configuration through `config.settings`, so
importing *any* of them executes this file first. That import ordering is the
mechanism, not a coincidence: both things below must happen before the first
HTTPS client or traced call is constructed, and this is the only place
guaranteed to run that early without every entrypoint remembering to call it.

1. Injects the operating system's trust store into Python's ssl module. This
   machine has a TLS-intercepting proxy/AV whose root CA is present in the
   Windows certificate store but not in certifi's bundle, so certifi-based
   verification fails with "unable to get local issuer certificate".
   truststore delegates verification to the OS store, which trusts that root.

2. Exports the LangSmith settings into `os.environ` (see
   `observability.tracing`). The LangSmith SDK reads its configuration from
   environment variables only — it never sees our `Settings` object — and
   `pydantic-settings` parses `.env` without exporting it. Without that bridge,
   tracing silently does nothing: `@traceable` never raises, it just drops the
   run on the floor.

Neither step is allowed to crash the process: a TLS-setup problem falls back to
certifi, and a bad LangSmith config costs observability, not function.
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
    from observability.tracing import setup_tracing

    setup_tracing()
    logger.debug("LangSmith environment exported from settings")
except Exception:
    logger.exception("Failed to export LangSmith environment; tracing may be disabled")
