"""One logging setup, shared by the API and every CLI."""

import logging

LOG_FORMAT = "%(asctime)s %(levelname)-8s %(name)s: %(message)s"
DEFAULT_LEVEL = logging.INFO


def setup_logging(level: int = DEFAULT_LEVEL) -> None:
    """Configure root logging.

    Safe to call more than once: `basicConfig` is a no-op once the root logger
    has handlers, so an entrypoint that calls this after uvicorn has already
    configured logging will not duplicate handlers.

    Never raises — failing to configure logging must not stop the process that
    was about to do the actual work.
    """
    try:
        logging.basicConfig(level=level, format=LOG_FORMAT)
    except Exception:  # noqa: BLE001 — logging is what failed, so there is no logger to use
        print("WARNING: logging configuration failed; using library defaults")
