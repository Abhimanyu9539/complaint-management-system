"""Query objects: the only place raw table access lives. One module per table."""

from datetime import UTC, datetime

# Errors are stored in a TEXT column; a stack-trace-sized message would only bloat the row.
ERROR_MAX_CHARS = 2000


class NotFound(LookupError):
    """No row with that id. The API maps it to 404."""


def utc_now_iso() -> str:
    """Timestamp in the format the `timestamptz` columns expect."""
    return datetime.now(UTC).isoformat()
