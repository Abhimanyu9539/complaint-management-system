"""Incoming email. n8n reads the support mailbox and posts each message here.

Guarded by a shared secret in `X-Inbound-Secret` (see `_check_secret`, the one
place to swap in an HMAC later). Unset in settings, inbound email is off.
"""

import hmac
import logging

from fastapi import APIRouter, BackgroundTasks, Header, HTTPException

from cms.config.settings import get_settings
from cms.schemas.emails import InboundEmailRequest, InboundEmailResult
from cms.services import email_intake, ticket_pipeline

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/emails", tags=["emails"])

DISABLED = "Inbound email is off: INBOUND_EMAIL_SECRET is not set."
BAD_SECRET = "Missing or wrong X-Inbound-Secret."
FAILED = "The email could not be filed. Check the server log."


def _check_secret(secret: str | None) -> None:
    expected = get_settings().inbound_email_secret
    if not expected:
        raise HTTPException(status_code=503, detail=DISABLED)
    if not secret or not hmac.compare_digest(secret.encode(), expected.encode()):
        logger.warning("Inbound email refused: wrong secret")
        raise HTTPException(status_code=401, detail=BAD_SECRET)


@router.post("/inbound", response_model=InboundEmailResult)
async def inbound_email(
    payload: InboundEmailRequest,
    background_tasks: BackgroundTasks,
    x_inbound_secret: str | None = Header(default=None),
) -> InboundEmailResult:
    """File one email. A new complaint or a department's answer is then drafted in the background."""
    _check_secret(x_inbound_secret)

    try:
        result, trigger = await email_intake.ingest_email(payload)
    except Exception:
        # The 500 makes n8n retry.
        logger.exception("Inbound email %s could not be filed", payload.message_id)
        raise HTTPException(status_code=500, detail=FAILED) from None

    if trigger and result.ticket_id:
        background_tasks.add_task(ticket_pipeline.process_ticket, result.ticket_id, trigger)
    return result
