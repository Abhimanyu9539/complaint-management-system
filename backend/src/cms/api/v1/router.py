"""Mounts every route: `/health` unversioned for probes, the rest under `/api/v1`.

`/admin/*` is admins only. The other routers check the agent per route, because each has a public
exception: the customer form and n8n's `/emails/inbound`.
"""

from fastapi import APIRouter, Depends

from cms.api.deps import require_admin
from cms.api.v1.routes import admin, chat, departments, emails, health, me, tickets

V1_PREFIX = "/api/v1"

api_router = APIRouter()

# Unversioned — see the module docstring.
api_router.include_router(health.router)

# Versioned business routes.
api_router.include_router(admin.router, prefix=V1_PREFIX, dependencies=[Depends(require_admin)])
api_router.include_router(chat.router, prefix=V1_PREFIX)
api_router.include_router(departments.router, prefix=V1_PREFIX)
api_router.include_router(emails.router, prefix=V1_PREFIX)
api_router.include_router(me.router, prefix=V1_PREFIX)
api_router.include_router(tickets.router, prefix=V1_PREFIX)
