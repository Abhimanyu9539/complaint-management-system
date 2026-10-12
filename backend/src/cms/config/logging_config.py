"""One logging setup for the API and every CLI: JSON or text, tagged with the request, ticket and run."""

import json
import logging
from datetime import UTC, datetime

from cms.config.settings import get_settings
from cms.observability.context import request_id_var, run_id_var, ticket_id_var

TEXT_FORMAT = "%(asctime)s %(levelname)-8s %(name)s%(ids)s: %(message)s"
DEFAULT_LEVEL = "INFO"
DEFAULT_FORMAT = "text"

# Attributes every LogRecord has. Anything else on a record came from `extra=` and is logged as a field.
# `color_message` is uvicorn's copy of the message with terminal colour codes.
STANDARD_ATTRS = frozenset(logging.makeLogRecord({}).__dict__) | {
    "message",
    "asctime",
    "ids",
    "color_message",
}
ID_FIELDS = ("request_id", "ticket_id", "run_id")

# uvicorn configures these before the app is imported; they are pointed at the root handler instead.
UVICORN_LOGGERS = ("uvicorn", "uvicorn.error", "uvicorn.access")


class ContextFilter(logging.Filter):
    """Copy the current request, ticket and run ids onto the record."""

    def filter(self, record: logging.LogRecord) -> bool:
        record.request_id = request_id_var.get()
        record.ticket_id = ticket_id_var.get()
        record.run_id = run_id_var.get()
        ids = " ".join(f"{name}={getattr(record, name)}" for name in ID_FIELDS if getattr(record, name))
        record.ids = f" [{ids}]" if ids else ""
        return True


class JsonFormatter(logging.Formatter):
    """One JSON object per line: time, level, logger, message, the ids that are set, any `extra` fields."""

    def format(self, record: logging.LogRecord) -> str:
        entry = {
            "ts": datetime.fromtimestamp(record.created, UTC).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }
        entry.update({key: value for key, value in record.__dict__.items() if key not in STANDARD_ATTRS})
        for name in ID_FIELDS:
            if entry.get(name) is None:
                entry.pop(name, None)
        if record.exc_info:
            entry["exc_info"] = self.formatException(record.exc_info)
        return json.dumps(entry, default=str)


def _configured_level_and_format() -> tuple[str, str]:
    """Read from settings; the defaults if settings cannot load, so logging still works."""
    try:
        settings = get_settings()
        return settings.log_level.upper(), settings.log_format
    except Exception:  # noqa: BLE001 — a broken config must not stop logging; the real error surfaces later
        return DEFAULT_LEVEL, DEFAULT_FORMAT


def setup_logging(level: int | str | None = None) -> None:
    """Configure root logging. Safe to call more than once, and never raises."""
    try:
        configured_level, log_format = _configured_level_and_format()
        handler = logging.StreamHandler()
        handler.addFilter(ContextFilter())
        handler.setFormatter(JsonFormatter() if log_format == "json" else logging.Formatter(TEXT_FORMAT))
        # `force` replaces an earlier handler instead of adding a second one.
        logging.basicConfig(level=level or configured_level, handlers=[handler], force=True)

        for name in UVICORN_LOGGERS:
            uvicorn_logger = logging.getLogger(name)
            uvicorn_logger.handlers.clear()
            uvicorn_logger.propagate = True
        # The request-id middleware writes the access line, with the id and the duration.
        logging.getLogger("uvicorn.access").setLevel(logging.WARNING)
    except Exception:  # noqa: BLE001 — logging is what failed, so there is no logger to use
        print("WARNING: logging configuration failed; using library defaults")
