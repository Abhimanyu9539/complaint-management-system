"""Read-only admin endpoints, backing the frontend's admin panel.

Every handler is deliberately sync `def`, not `async def`. `health.py` is async
because it uses `httpx.AsyncClient`; the supabase client and the Qdrant client
used here are both *blocking*. A blocking call inside `async def` stalls the
whole event loop for every concurrent request, which is the easiest way to make
an API mysteriously slow. Sync handlers are dispatched to FastAPI's threadpool,
which is correct for this.

Error shape: FastAPI's `{"detail": ...}`. lld.md §4 specifies RFC 7807
`application/problem+json`, and nothing in the codebase implements it yet;
building a problem+json layer for four GETs would be inventing a convention
rather than following one.
TODO(lld.md §4): adopt problem+json across the API.
  The trigger this TODO named — "when the first write endpoints land" — has now
  fired: `routes/tickets.py` carries POST handlers. It was deliberately not
  taken there, because converting one router while these six endpoints keep the
  old shape would make clients parse two error formats. The move is worth doing
  as one change across every route, including the 409 and 422 the ticket state
  machine raises, which is where problem+json actually earns its extra fields.

Auth: these routes are unauthenticated, because the whole API is. lld.md §4
requires `role = admin` on `/admin/*`. See `backend/docs/admin-api.md` for the
intended `Depends(require_admin)` dependency — do not expose this publicly
before it exists.
"""

import logging
from typing import Literal

from fastapi import APIRouter, HTTPException, Query

from cms.schemas.admin import (
    DepartmentOptionPage,
    DocumentOptionPage,
    EscalationSummaryResponse,
    IngestionSummaryResponse,
    JobPage,
    OverviewResponse,
    StorageResponse,
)
from cms.services import admin_stats

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/admin", tags=["admin"])

# The dashboard polls these, so their failures land on an ops screen rather than
# in front of a user who could act on a stack trace: the traceback is logged
# server-side and the response body stays generic.
UNAVAILABLE = "That admin view is unavailable right now. Check the server log."


@router.get("/overview", response_model=OverviewResponse)
def get_overview() -> OverviewResponse:
    """Document counts, job counts, the live queue and stuck documents."""
    try:
        return admin_stats.build_overview()
    except Exception:
        logger.exception("Failed to build the admin overview")
        raise HTTPException(status_code=503, detail=UNAVAILABLE) from None


@router.get("/storage", response_model=StorageResponse)
def get_storage() -> StorageResponse:
    """Qdrant collection stats, chunk-row counts and stored policy files.

    Reaching Qdrant is the slow part, and an unreachable vector store does not
    fail this endpoint — the collection rows come back with `reachable: false`
    so the Supabase half still renders.
    """
    try:
        return admin_stats.build_storage()
    except Exception:
        logger.exception("Failed to build the admin storage view")
        raise HTTPException(status_code=503, detail=UNAVAILABLE) from None


@router.get("/ingestion/jobs", response_model=JobPage)
def list_ingestion_jobs(
    status: Literal["queued", "running", "done", "failed"] | None = Query(None),
    doc_type: Literal["case", "policy"] | None = Query(None),
    search: str | None = Query(None, max_length=200),
    limit: int = Query(25, ge=1, le=100),
    offset: int = Query(0, ge=0),
) -> JobPage:
    """A page of the append-only ingestion ops log, newest first."""
    try:
        return admin_stats.build_job_page(
            status=status, doc_type=doc_type, search=search, limit=limit, offset=offset
        )
    except Exception:
        logger.exception("Failed to list ingestion jobs")
        raise HTTPException(status_code=503, detail=UNAVAILABLE) from None


@router.get("/ingestion/summary", response_model=IngestionSummaryResponse)
def get_ingestion_summary(days: int = Query(30, ge=1, le=90)) -> IngestionSummaryResponse:
    """Per-day job counts, duration percentiles and success rate over a window.

    Capped at 90 days: the window is aggregated in memory, and the repository
    read behind it is a single unpaged select.
    """
    try:
        return admin_stats.build_ingestion_summary(days)
    except Exception:
        logger.exception("Failed to build the ingestion summary for %d days", days)
        raise HTTPException(status_code=503, detail=UNAVAILABLE) from None


@router.get("/documents", response_model=DocumentOptionPage)
def list_documents(
    doc_type: Literal["case", "policy"] = Query(...),
    limit: int = Query(200, ge=1, le=500),
) -> DocumentOptionPage:
    """Ids and titles for the single-document ingest picker."""
    try:
        return DocumentOptionPage(items=admin_stats.build_document_options(doc_type, limit))
    except Exception:
        logger.exception("Failed to list %s documents", doc_type)
        raise HTTPException(status_code=503, detail=UNAVAILABLE) from None


@router.get("/escalation", response_model=EscalationSummaryResponse)
def get_escalation_summary(days: int = Query(30, ge=1, le=90)) -> EscalationSummaryResponse:
    """The escalation rate, the ticket funnel and the per-department split.

    cms.md §2's north-star metric. Note that `escalation_rate` is null rather
    than zero until at least one ticket has been resolved — clients must render
    that as "no data", never as 0%.
    """
    try:
        return admin_stats.build_escalation_summary(days)
    except Exception:
        logger.exception("Failed to build the escalation summary for %d days", days)
        raise HTTPException(status_code=503, detail=UNAVAILABLE) from None


@router.get("/departments", response_model=DepartmentOptionPage)
def list_departments() -> DepartmentOptionPage:
    """The closed set of twelve routing targets, for the escalate picker."""
    try:
        return DepartmentOptionPage(items=admin_stats.build_departments())
    except Exception:
        logger.exception("Failed to list departments")
        raise HTTPException(status_code=503, detail=UNAVAILABLE) from None
