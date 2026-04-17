"""Read-only admin endpoints, backing the frontend's admin panel.

Every handler is `async def`, and everything below them is awaited: the
supabase client is `AsyncClient` (see `db/session.py`) and Qdrant is reached
through `AsyncQdrantClient`. Concurrency here is bounded by the event loop
rather than by FastAPI's threadpool, which is all the sync handlers these
replaced could use.

The one call that is *not* natively async is the vector-store embed/upsert on
the ingestion path; it is thread-offloaded rather than awaited inline. See
`ingestion/load/vector_loader.py`.

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

from fastapi import APIRouter, BackgroundTasks, HTTPException, Query

from cms.schemas.admin import (
    DepartmentOptionPage,
    DocumentOptionPage,
    EscalationSummaryResponse,
    IngestionSummaryResponse,
    JobPage,
    OverviewResponse,
    StorageResponse,
    TriggerIngestionRequest,
    TriggerIngestionResponse,
)
from cms.services import admin_ingest, admin_stats

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/admin", tags=["admin"])

# The dashboard polls these, so their failures land on an ops screen rather than
# in front of a user who could act on a stack trace: the traceback is logged
# server-side and the response body stays generic.
UNAVAILABLE = "That admin view is unavailable right now. Check the server log."

# `resolve_seed_dir` raises this when the seed corpus isn't mounted — a
# deployment problem, not "that document doesn't exist" (which would be a 422)
# nor a generic Supabase-flavoured 503. Named separately so an operator isn't
# sent to debug the database for what is actually a missing SEED_DATA_DIR.
SEED_CORPUS_UNAVAILABLE = (
    "The seed corpus directory is not readable. Set SEED_DATA_DIR — see the server log "
    "for the paths tried."
)


@router.get("/overview", response_model=OverviewResponse)
async def get_overview() -> OverviewResponse:
    """Document counts, job counts, the live queue and stuck documents."""
    try:
        return await admin_stats.build_overview()
    except Exception:
        logger.exception("Failed to build the admin overview")
        raise HTTPException(status_code=503, detail=UNAVAILABLE) from None


@router.get("/storage", response_model=StorageResponse)
async def get_storage() -> StorageResponse:
    """Qdrant collection stats, chunk-row counts and stored policy files.

    Reaching Qdrant is the slow part, and an unreachable vector store does not
    fail this endpoint — the collection rows come back with `reachable: false`
    so the Supabase half still renders.
    """
    try:
        return await admin_stats.build_storage()
    except Exception:
        logger.exception("Failed to build the admin storage view")
        raise HTTPException(status_code=503, detail=UNAVAILABLE) from None


@router.get("/ingestion/jobs", response_model=JobPage)
async def list_ingestion_jobs(
    status: Literal["queued", "running", "done", "failed"] | None = Query(None),
    doc_type: Literal["case", "policy"] | None = Query(None),
    search: str | None = Query(None, max_length=200),
    limit: int = Query(25, ge=1, le=100),
    offset: int = Query(0, ge=0),
) -> JobPage:
    """A page of the append-only ingestion ops log, newest first."""
    try:
        return await admin_stats.build_job_page(
            status=status, doc_type=doc_type, search=search, limit=limit, offset=offset
        )
    except Exception:
        logger.exception("Failed to list ingestion jobs")
        raise HTTPException(status_code=503, detail=UNAVAILABLE) from None


@router.post("/ingestion/jobs", response_model=TriggerIngestionResponse, status_code=202)
async def trigger_ingestion_job(
    payload: TriggerIngestionRequest, background_tasks: BackgroundTasks
) -> TriggerIngestionResponse:
    """Queue a manual ingest. Returns before the embedding run finishes — see admin-api.md §4."""
    try:
        return await admin_ingest.trigger_ingestion(payload, background_tasks)
    except admin_ingest.UnknownDocument as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from None
    except FileNotFoundError:
        logger.exception("Seed corpus directory not readable while queuing an ingestion job")
        raise HTTPException(status_code=503, detail=SEED_CORPUS_UNAVAILABLE) from None
    except Exception:
        logger.exception("Failed to queue an ingestion job")
        raise HTTPException(status_code=503, detail=UNAVAILABLE) from None


@router.post(
    "/ingestion/jobs/{job_id}/retry", response_model=TriggerIngestionResponse, status_code=202
)
async def retry_ingestion_job(job_id: str, background_tasks: BackgroundTasks) -> TriggerIngestionResponse:
    """Re-ingest the document a finished/failed job referenced — see admin-api.md §5."""
    try:
        return await admin_ingest.retry_job(job_id, background_tasks)
    except LookupError:
        raise HTTPException(status_code=404, detail="No such ingestion job.") from None
    except Exception:
        logger.exception("Failed to retry ingestion job %s", job_id)
        raise HTTPException(status_code=503, detail=UNAVAILABLE) from None


@router.post(
    "/documents/{doc_type}/{document_id}/rerun",
    response_model=TriggerIngestionResponse,
    status_code=202,
)
async def rerun_stuck_document(
    doc_type: Literal["case", "policy"], document_id: str, background_tasks: BackgroundTasks
) -> TriggerIngestionResponse:
    """Re-run a document stuck at `processing` — the dashboard queue panel's action.

    Distinct from `POST /ingestion/jobs` (`mode="document"` seeds a corpus file
    by `source_ref`) and from the retry route (which resolves an existing job
    row): this acts directly on the document's own Postgres id, which is what
    the queue panel's `queue.stuck[].id` already is — see admin-api.md §4a.
    """
    try:
        return await admin_ingest.rerun_stuck_document(doc_type, document_id, background_tasks)
    except admin_ingest.UnknownDocument as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from None
    except Exception:
        logger.exception("Failed to queue a re-run for %s %s", doc_type, document_id)
        raise HTTPException(status_code=503, detail=UNAVAILABLE) from None


@router.get("/ingestion/summary", response_model=IngestionSummaryResponse)
async def get_ingestion_summary(days: int = Query(30, ge=1, le=90)) -> IngestionSummaryResponse:
    """Per-day job counts, duration percentiles and success rate over a window.

    Capped at 90 days: the window is aggregated in memory, and the repository
    read behind it is a single unpaged select.
    """
    try:
        return await admin_stats.build_ingestion_summary(days)
    except Exception:
        logger.exception("Failed to build the ingestion summary for %d days", days)
        raise HTTPException(status_code=503, detail=UNAVAILABLE) from None


@router.get("/documents", response_model=DocumentOptionPage)
async def list_documents(
    doc_type: Literal["case", "policy"] = Query(...),
    limit: int = Query(200, ge=1, le=500),
) -> DocumentOptionPage:
    """Seed-corpus entries and their index status, for the single-document ingest picker."""
    try:
        return DocumentOptionPage(items=await admin_stats.build_document_options(doc_type, limit))
    except FileNotFoundError:
        logger.exception("Seed corpus directory not readable while listing %s documents", doc_type)
        raise HTTPException(status_code=503, detail=SEED_CORPUS_UNAVAILABLE) from None
    except Exception:
        logger.exception("Failed to list %s documents", doc_type)
        raise HTTPException(status_code=503, detail=UNAVAILABLE) from None


@router.get("/escalation", response_model=EscalationSummaryResponse)
async def get_escalation_summary(days: int = Query(30, ge=1, le=90)) -> EscalationSummaryResponse:
    """The escalation rate, the ticket funnel and the per-department split.

    cms.md §2's north-star metric. Note that `escalation_rate` is null rather
    than zero until at least one ticket has been resolved — clients must render
    that as "no data", never as 0%.
    """
    try:
        return await admin_stats.build_escalation_summary(days)
    except Exception:
        logger.exception("Failed to build the escalation summary for %d days", days)
        raise HTTPException(status_code=503, detail=UNAVAILABLE) from None


@router.get("/departments", response_model=DepartmentOptionPage)
async def list_departments() -> DepartmentOptionPage:
    """The closed set of twelve routing targets, for the escalate picker."""
    try:
        return DepartmentOptionPage(items=await admin_stats.build_departments())
    except Exception:
        logger.exception("Failed to list departments")
        raise HTTPException(status_code=503, detail=UNAVAILABLE) from None
