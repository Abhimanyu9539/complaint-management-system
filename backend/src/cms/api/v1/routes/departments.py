"""The twelve routing targets, for the workbench's escalate picker. Any signed-in agent."""

import logging

from fastapi import APIRouter, Depends, HTTPException

from cms.api.deps import get_current_user
from cms.schemas.admin import DepartmentOptionPage
from cms.services import admin_stats

logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/departments", tags=["departments"], dependencies=[Depends(get_current_user)]
)

UNAVAILABLE = "Departments are unavailable right now. Check the server log."


@router.get("", response_model=DepartmentOptionPage)
async def list_departments() -> DepartmentOptionPage:
    try:
        return DepartmentOptionPage(items=await admin_stats.build_departments())
    except Exception:
        logger.exception("Failed to list departments")
        raise HTTPException(status_code=503, detail=UNAVAILABLE) from None
