"""The signed-in caller, as every protected route sees it."""

from typing import Literal

from pydantic import BaseModel, ConfigDict


class CurrentUser(BaseModel):
    """A verified Supabase user with an active `profiles` row."""

    model_config = ConfigDict(frozen=True)

    id: str
    email: str
    display_name: str | None = None
    role: Literal["agent", "admin"]
