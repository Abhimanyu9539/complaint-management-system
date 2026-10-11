"""Dependency checks for `/health/ready` and the admin health panel. Each one is time-boxed."""

import asyncio
import logging
from collections.abc import Awaitable, Callable, Iterable

import httpx

from cms.config.settings import get_settings
from cms.db.mongo import get_mongo_client
from cms.db.repositories import departments
from cms.db.session import get_supabase
from cms.retrieval.vector_store.qdrant_store import get_async_qdrant_client
from cms.schemas.health import DependencyCheck
from cms.services import email_sender

logger = logging.getLogger(__name__)

OK = "ok"
DISABLED = "disabled"
ERROR = "error"
TIMED_OUT = "timed out"
# OpenRouter's key-info endpoint: proves the key works and costs no credits.
OPENROUTER_KEY_PATH = "/key"


async def _check_supabase() -> str:
    # A real PostgREST read, so the service key and the schema are covered, not just reachability.
    await get_supabase().table(departments.TABLE).select("id").limit(1).execute()
    return OK


async def _check_qdrant() -> str:
    await get_async_qdrant_client().get_collections()
    return OK


async def _check_mongo() -> str:
    if not get_settings().chat_memory_enabled:
        return DISABLED
    await asyncio.to_thread(get_mongo_client().admin.command, "ping")
    return OK


async def _check_openrouter() -> str:
    settings = get_settings()
    async with httpx.AsyncClient(timeout=settings.health_check_timeout_seconds) as client:
        response = await client.get(
            f"{settings.openrouter_base_url.rstrip('/')}{OPENROUTER_KEY_PATH}",
            headers={"Authorization": f"Bearer {settings.open_router_api_key}"},
        )
        response.raise_for_status()
    return OK


async def _check_smtp() -> str:
    await asyncio.to_thread(email_sender.check_connection)
    return OK


CHECKS: dict[str, Callable[[], Awaitable[str]]] = {
    "supabase": _check_supabase,
    "qdrant": _check_qdrant,
    "mongo": _check_mongo,
    "openrouter": _check_openrouter,
    "smtp": _check_smtp,
}


async def _run(name: str) -> DependencyCheck:
    """One check. The cause of a failure is logged; only its type is returned."""
    timeout = get_settings().health_check_timeout_seconds
    try:
        status = await asyncio.wait_for(CHECKS[name](), timeout)
    except TimeoutError:
        logger.warning("health: %s did not answer within %ss", name, timeout)
        return DependencyCheck(status=ERROR, detail=TIMED_OUT)
    except Exception as exc:
        logger.warning("health: the %s check failed", name, exc_info=True)
        return DependencyCheck(status=ERROR, detail=type(exc).__name__)
    return DependencyCheck(status=status)


async def check_dependencies(names: Iterable[str]) -> dict[str, DependencyCheck]:
    """Run the named checks at once. Never raises: a failure is an `error` result."""
    names = list(names)
    results = await asyncio.gather(*(_run(name) for name in names))
    return dict(zip(names, results, strict=True))


def any_down(checks: dict[str, DependencyCheck]) -> bool:
    return any(check.status == ERROR for check in checks.values())
