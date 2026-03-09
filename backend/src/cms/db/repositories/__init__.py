"""Query objects — the only place raw table access lives.

Everything above this package asks for a document or records a status change;
nothing above it names a column or builds a filter. That is what keeps a schema
change to a one-package edit instead of a grep across the pipeline.

One module per table, except the two chunk tables, which share one because they
share a shape.
"""

from datetime import UTC, datetime

# Errors are stored in a TEXT column, but a stack-trace-sized message helps
# nobody and would bloat the row. Truncate every error the repositories persist.
ERROR_MAX_CHARS = 2000


def utc_now_iso() -> str:
    """Timestamp in the format the `timestamptz` columns expect."""
    return datetime.now(UTC).isoformat()
