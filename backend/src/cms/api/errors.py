"""Turns service errors into HTTP responses, so routes need no try/except of their own."""

import logging
from collections.abc import Awaitable, Callable

from fastapi import FastAPI, Request, Response
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from fastapi.routing import APIRoute
from starlette.exceptions import HTTPException

from cms.config.settings import get_settings
from cms.db.repositories import NotFound
from cms.services.admin_ingest import UnknownDocument
from cms.services.email_sender import EmailSendError
from cms.services.reply_service import DraftConflict, InvalidReply
from cms.services.ticket_service import IllegalTransition, StatusChanged, UnknownDepartment

logger = logging.getLogger(__name__)

# Each error's own message is written for a person, so it is sent as the `detail`.
STATUS_BY_ERROR: dict[type[Exception], int] = {
    NotFound: 404,
    IllegalTransition: 409,
    StatusChanged: 409,
    DraftConflict: 409,
    UnknownDepartment: 422,
    InvalidReply: 422,
    UnknownDocument: 422,
}

# Errors with a response of their own. Anything else is unexpected.
EXPECTED_ERRORS: tuple[type[Exception], ...] = (
    HTTPException,
    RequestValidationError,
    EmailSendError,
    *STATUS_BY_ERROR,
)


def _domain_handler(status: int) -> Callable[[Request, Exception], Awaitable[JSONResponse]]:
    async def handle(request: Request, exc: Exception) -> JSONResponse:
        logger.info("%s %s -> %d: %s", request.method, request.url.path, status, exc)
        return JSONResponse({"detail": str(exc)}, status_code=status)

    return handle


async def _email_failed(request: Request, exc: Exception) -> JSONResponse:
    # The cause is logged by `email_sender`; it names SMTP internals, so it is not sent.
    logger.warning("%s %s -> 502: %s", request.method, request.url.path, exc)
    return JSONResponse({"detail": get_settings().email_send_failed_message}, status_code=502)


class ErrorRoute(APIRoute):
    """Logs an unexpected error and answers 503.

    Done in the route rather than with an `Exception` handler: that one runs outside
    the CORS middleware, so the browser would see a CORS failure instead of the message.
    """

    def get_route_handler(self) -> Callable[[Request], Awaitable[Response]]:
        handler = super().get_route_handler()

        async def run(request: Request) -> Response:
            try:
                return await handler(request)
            except EXPECTED_ERRORS:
                raise
            except Exception:
                logger.exception("%s %s failed", request.method, request.url.path)
                raise HTTPException(
                    status_code=503, detail=get_settings().api_unavailable_message
                ) from None

        return run


def register_error_handlers(app: FastAPI) -> None:
    """Map each service error to its status code."""
    for error, status in STATUS_BY_ERROR.items():
        app.add_exception_handler(error, _domain_handler(status))
    app.add_exception_handler(EmailSendError, _email_failed)
