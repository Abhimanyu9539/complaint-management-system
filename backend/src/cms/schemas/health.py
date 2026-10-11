"""Responses of the health probes and the admin health panel."""

from typing import Literal

from pydantic import BaseModel

DependencyStatus = Literal["ok", "error", "disabled"]


class DependencyCheck(BaseModel):
    """One dependency's result. `detail` is the error's type or "timed out", never its message."""

    status: DependencyStatus
    detail: str | None = None


class LiveResponse(BaseModel):
    status: Literal["ok"] = "ok"


class ReadyResponse(BaseModel):
    """Public, so a status per dependency and nothing more."""

    status: Literal["ready", "unavailable"]
    dependencies: dict[str, DependencyStatus]


class DependencyHealthResponse(BaseModel):
    """Admins only: every dependency, with the error's type when one is down."""

    status: Literal["ok", "degraded"]
    dependencies: dict[str, DependencyCheck]
