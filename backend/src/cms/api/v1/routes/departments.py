"""The twelve routing targets, for the workbench's escalate picker. Any signed-in agent."""

from fastapi import APIRouter, Depends

from cms.api.deps import get_current_user
from cms.api.errors import ErrorRoute
from cms.schemas.admin import DepartmentOptionPage
from cms.services import admin_stats

router = APIRouter(
    prefix="/departments",
    tags=["departments"],
    dependencies=[Depends(get_current_user)],
    route_class=ErrorRoute,
)


@router.get("", response_model=DepartmentOptionPage)
async def list_departments() -> DepartmentOptionPage:
    return DepartmentOptionPage(items=await admin_stats.build_departments())
