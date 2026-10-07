"""Admin panel endpoints. Admins only: `router.py` applies `require_admin` to the whole router.

Errors are mapped to status codes in `cms.api.errors`.
"""

import logging
from typing import Literal

from fastapi import APIRouter, BackgroundTasks, HTTPException, Query

from cms.api.errors import ErrorRoute
from cms.config.settings import get_settings
from cms.schemas.admin import (
    AgentRunPage,
    AgentSummaryResponse,
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

router = APIRouter(prefix="/admin", tags=["admin"], route_class=ErrorRoute)


def _seed_corpus_unavailable() -> HTTPException:
    """A missing SEED_DATA_DIR is a deployment problem, so it gets its own 503 message."""
    return HTTPException(status_code=503, detail=get_settings().seed_corpus_unavailable_message)


@router.get("/overview", response_model=OverviewResponse)
async def get_overview() -> OverviewResponse:
    """Document counts, job counts, the live queue and stuck documents."""
    return await admin_stats.build_overview()


@router.get("/storage", response_model=StorageResponse)
async def get_storage() -> StorageResponse:
    """Qdrant collection stats, chunk-row counts and stored policy files.

    An unreachable Qdrant does not fail this: its rows come back with `reachable: false`.
    """
    return await admin_stats.build_storage()


@router.get("/ingestion/jobs", response_model=JobPage)
async def list_ingestion_jobs(
    status: Literal["queued", "running", "done", "failed"] | None = Query(None),
    doc_type: Literal["case", "policy"] | None = Query(None),
    search: str | None = Query(None, max_length=200),
    limit: int = Query(25, ge=1, le=100),
    offset: int = Query(0, ge=0),
) -> JobPage:
    """A page of the append-only ingestion log, newest first."""
    return await admin_stats.build_job_page(
        status=status, doc_type=doc_type, search=search, limit=limit, offset=offset
    )


@router.post("/ingestion/jobs", response_model=TriggerIngestionResponse, status_code=202)
async def trigger_ingestion_job(
    payload: TriggerIngestionRequest, background_tasks: BackgroundTasks
) -> TriggerIngestionResponse:
    """Queue a manual ingest. Returns before the embedding run finishes."""
    try:
        return await admin_ingest.trigger_ingestion(payload, background_tasks)
    except FileNotFoundError:
        logger.exception("Seed corpus not readable while queuing an ingestion job")
        raise _seed_corpus_unavailable() from None


@router.post(
    "/ingestion/jobs/{job_id}/retry", response_model=TriggerIngestionResponse, status_code=202
)
async def retry_ingestion_job(job_id: str, background_tasks: BackgroundTasks) -> TriggerIngestionResponse:
    """Re-ingest the document a finished or failed job referenced."""
    return await admin_ingest.retry_job(job_id, background_tasks)


@router.post(
    "/documents/{doc_type}/{document_id}/rerun",
    response_model=TriggerIngestionResponse,
    status_code=202,
)
async def rerun_stuck_document(
    doc_type: Literal["case", "policy"], document_id: str, background_tasks: BackgroundTasks
) -> TriggerIngestionResponse:
    """Re-run a document stuck at `processing`, by its own id (the dashboard queue panel's action)."""
    return await admin_ingest.rerun_stuck_document(doc_type, document_id, background_tasks)


@router.get("/ingestion/summary", response_model=IngestionSummaryResponse)
async def get_ingestion_summary(days: int = Query(30, ge=1, le=90)) -> IngestionSummaryResponse:
    """Per-day job counts, duration percentiles and success rate. Capped at 90 days (aggregated in memory)."""
    return await admin_stats.build_ingestion_summary(days)


@router.get("/documents", response_model=DocumentOptionPage)
async def list_documents(
    doc_type: Literal["case", "policy"] = Query(...),
    limit: int = Query(200, ge=1, le=500),
) -> DocumentOptionPage:
    """Seed-corpus entries and their index status, for the single-document ingest picker."""
    try:
        return DocumentOptionPage(items=await admin_stats.build_document_options(doc_type, limit))
    except FileNotFoundError:
        logger.exception("Seed corpus not readable while listing %s documents", doc_type)
        raise _seed_corpus_unavailable() from None


@router.get("/escalation", response_model=EscalationSummaryResponse)
async def get_escalation_summary(days: int = Query(30, ge=1, le=90)) -> EscalationSummaryResponse:
    """The escalation rate, the ticket funnel and the per-department split.

    `escalation_rate` is null, not zero, until a ticket has been resolved: render it as "no data".
    """
    return await admin_stats.build_escalation_summary(days)


@router.get("/agent/runs", response_model=AgentRunPage)
async def list_agent_runs(
    status: Literal["succeeded", "no_match", "blocked", "failed"] | None = Query(None),
    search: str | None = Query(None, max_length=200),
    limit: int = Query(25, ge=1, le=100),
    offset: int = Query(0, ge=0),
) -> AgentRunPage:
    """A page of ticket-graph runs, newest first. `search` takes a ticket number or subject text."""
    return await admin_stats.build_agent_run_page(
        status=status, search=search, limit=limit, offset=offset
    )


@router.get("/agent/summary", response_model=AgentSummaryResponse)
async def get_agent_summary(days: int = Query(7, ge=1, le=90)) -> AgentSummaryResponse:
    """Run counts, graph latency percentiles and per-node median latency over a window."""
    return await admin_stats.build_agent_summary(days)
