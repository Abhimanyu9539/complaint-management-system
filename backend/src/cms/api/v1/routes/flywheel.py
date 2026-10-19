"""The daily minting job: Airflow lists a day's resolved tickets, then mints them one by one.

Off while `FLYWHEEL_JOB_SECRET` is unset. A failed mint answers 500, which makes Airflow retry.
"""

import hmac
import logging
from datetime import date

from fastapi import APIRouter, Header, HTTPException, Query

from cms.config.settings import get_settings
from cms.schemas.flywheel import FlywheelCandidates, MintResult
from cms.services import case_minting

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/flywheel", tags=["flywheel"])

DISABLED = "The minting job is off: FLYWHEEL_JOB_SECRET is not set."
BAD_SECRET = "Missing or wrong X-Job-Secret."
LIST_FAILED = "The resolved tickets could not be listed. Check the server log."
MINT_FAILED = "The case could not be minted. Check the server log."


def _check_secret(secret: str | None) -> None:
    expected = get_settings().flywheel_job_secret
    if not expected:
        raise HTTPException(status_code=503, detail=DISABLED)
    if not secret or not hmac.compare_digest(secret.encode(), expected.encode()):
        logger.warning("Flywheel job refused: wrong secret")
        raise HTTPException(status_code=401, detail=BAD_SECRET)


@router.get("/candidates", response_model=FlywheelCandidates)
async def list_candidates(
    day: date = Query(description="The IST day whose resolved tickets to mint."),
    x_job_secret: str | None = Header(default=None),
) -> FlywheelCandidates:
    """The tickets resolved on `day` and still resolved, oldest first."""
    _check_secret(x_job_secret)
    try:
        ticket_ids = await case_minting.list_candidates(day)
    except Exception:
        logger.exception("Could not list the tickets resolved on %s", day)
        raise HTTPException(status_code=500, detail=LIST_FAILED) from None
    return FlywheelCandidates(day=day, ticket_ids=ticket_ids)


@router.post("/tickets/{ticket_id}/mint", response_model=MintResult)
async def mint_ticket(ticket_id: str, x_job_secret: str | None = Header(default=None)) -> MintResult:
    """Mint one ticket's case, refresh it, or skip it as a duplicate."""
    _check_secret(x_job_secret)
    try:
        return await case_minting.mint_case(ticket_id)
    except Exception:
        # Already recorded on the ticket; the 500 makes Airflow retry.
        logger.exception("Ticket %s: minting the case failed", ticket_id)
        raise HTTPException(status_code=500, detail=MINT_FAILED) from None
