"""Load-balancer probes: `/health/live` (the process is up) and `/health/ready` (it can serve).

Public, so errors are reported as a status only; the cause is in the log.
The admin panel's detailed view is `GET /api/v1/admin/health`.
"""

import logging

from fastapi import APIRouter, Response

from cms.config.settings import get_settings
from cms.schemas.health import LiveResponse, ReadyResponse
from cms.services import health_checks

logger = logging.getLogger(__name__)

router = APIRouter(tags=["health"])


@router.get("/health/live", response_model=LiveResponse)
async def live() -> LiveResponse:
    """Checks nothing else, so a dependency outage never gets the process restarted."""
    return LiveResponse()


@router.get("/health/ready", response_model=ReadyResponse, responses={503: {"model": ReadyResponse}})
async def ready(response: Response) -> ReadyResponse:
    """200 when every hard dependency answers, 503 when one does not."""
    checks = await health_checks.check_dependencies(get_settings().health_ready_dependencies)
    is_down = health_checks.any_down(checks)
    if is_down:
        response.status_code = 503
        logger.warning("health: not ready: %s", {name: check.status for name, check in checks.items()})
    return ReadyResponse(
        status="unavailable" if is_down else "ready",
        dependencies={name: check.status for name, check in checks.items()},
    )
