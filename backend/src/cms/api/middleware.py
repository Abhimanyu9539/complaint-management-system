"""Request-id middleware: tag every log line of a request with one id, echo it back, log the access line.

Plain ASGI rather than `BaseHTTPMiddleware`, so the chat's SSE stream is passed through unbuffered.
"""

import logging
import re
import time
from uuid import uuid4

from starlette.datastructures import Headers, MutableHeaders
from starlette.types import ASGIApp, Message, Receive, Scope, Send

from cms.config.settings import get_settings
from cms.observability.context import request_id_var

logger = logging.getLogger(__name__)


class RequestIdMiddleware:
    def __init__(self, app: ASGIApp) -> None:
        self.app = app
        settings = get_settings()
        self.header = settings.request_id_header
        self.pattern = re.compile(settings.request_id_pattern)
        self.skip_paths = frozenset(settings.access_log_skip_paths)

    def _request_id(self, scope: Scope) -> str:
        """The caller's id when it is safe to log, otherwise a new one."""
        incoming = Headers(scope=scope).get(self.header)
        if incoming and self.pattern.fullmatch(incoming):
            return incoming
        return uuid4().hex

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        request_id = self._request_id(scope)
        token = request_id_var.set(request_id)
        start = time.perf_counter()
        status = 500

        async def send_with_id(message: Message) -> None:
            nonlocal status
            if message["type"] == "http.response.start":
                status = message["status"]
                MutableHeaders(scope=message).append(self.header, request_id)
            await send(message)
            # Logged when the body is complete, before any background task runs.
            if message["type"] == "http.response.body" and not message.get("more_body", False):
                self._log_access(scope, status, start)

        try:
            await self.app(scope, receive, send_with_id)
        finally:
            request_id_var.reset(token)

    def _log_access(self, scope: Scope, status: int, start: float) -> None:
        path = scope["path"]
        if path in self.skip_paths:
            return
        duration_ms = round((time.perf_counter() - start) * 1000)
        logger.info(
            "%s %s -> %d in %d ms",
            scope["method"],
            path,
            status,
            duration_ms,
            extra={"method": scope["method"], "path": path, "status": status, "duration_ms": duration_ms},
        )
