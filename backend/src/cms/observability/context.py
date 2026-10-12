"""The ids every log line carries: set per request, ticket and graph run, read by the log filter."""

from contextvars import ContextVar

request_id_var: ContextVar[str | None] = ContextVar("request_id", default=None)
ticket_id_var: ContextVar[str | None] = ContextVar("ticket_id", default=None)
run_id_var: ContextVar[str | None] = ContextVar("run_id", default=None)
