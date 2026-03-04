"""App package initialization.

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
