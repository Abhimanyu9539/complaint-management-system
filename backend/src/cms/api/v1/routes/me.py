"""The signed-in caller. The frontend reads it to learn the role."""

from fastapi import APIRouter, Depends

from cms.api.deps import get_current_user
from cms.schemas.auth import CurrentUser

router = APIRouter(tags=["auth"])


@router.get("/me", response_model=CurrentUser)
async def me(user: CurrentUser = Depends(get_current_user)) -> CurrentUser:
    return user
