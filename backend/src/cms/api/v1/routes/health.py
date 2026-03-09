import httpx
from fastapi import APIRouter
from qdrant_client import AsyncQdrantClient

from cms.config.settings import get_settings

router = APIRouter(tags=["health"])


@router.get("/health")
async def health() -> dict:
    return {"status": "ok"}


@router.get("/health/deps")
async def health_deps() -> dict:
    """Pings Supabase and Qdrant so a broken .env shows up here, not on the first real request."""
    settings = get_settings()
    results: dict[str, str] = {}

    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            # GoTrue's health endpoint needs no schema/tables to exist yet — safe before Step 2.
            resp = await client.get(
                f"{settings.supabase_url}/auth/v1/health",
                headers={"apikey": settings.supabase_publishable_key},
            )
            resp.raise_for_status()
        results["supabase"] = "ok"
    except Exception as exc:
        results["supabase"] = f"error: {exc}"

    try:
        qdrant = AsyncQdrantClient(
            url=settings.qdrant_url, api_key=settings.qdrant_api_key
        )
        try:
            # Listing collections proves connectivity without requiring one to exist yet (Step 3).
            await qdrant.get_collections()
        finally:
            await qdrant.close()
        results["qdrant"] = "ok"
    except Exception as exc:
        results["qdrant"] = f"error: {exc}"

    overall = "ok" if all(v == "ok" for v in results.values()) else "degraded"
    return {"status": overall, "dependencies": results}
