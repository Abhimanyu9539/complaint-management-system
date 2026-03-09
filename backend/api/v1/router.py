"""Aggregates every v1 route into the one router `main.py` mounts.

Business routes carry the `/api/v1` prefix the frontend already calls
(`/api/v1/chat`), applied here rather than in each route module so a future v2
is a second router, not an edit to every file.

Health is the deliberate exception: probes and uptime checks point at bare
`/health`, and versioning an infrastructure endpoint means every probe has to be
reconfigured the day the API version changes.
"""

from fastapi import APIRouter

from api.v1.routes import health

V1_PREFIX = "/api/v1"

api_router = APIRouter()

# Unversioned — see the module docstring.
api_router.include_router(health.router)

# Versioned business routes go here as they land, e.g.:
#   api_router.include_router(complaints.router, prefix=V1_PREFIX)
