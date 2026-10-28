"""`GET /metrics` for Prometheus. Public like `/health`: restrict it at the network in a deployment.

With `PROMETHEUS_MULTIPROC_DIR` set, the counts of every worker process are added up.
"""

import logging
import os

from fastapi import APIRouter, HTTPException, Response
from prometheus_client import CONTENT_TYPE_LATEST, CollectorRegistry, generate_latest, multiprocess

logger = logging.getLogger(__name__)

router = APIRouter(tags=["metrics"])

# Read by prometheus_client itself when it is imported, so it must be a real environment variable.
MULTIPROC_DIR_VAR = "PROMETHEUS_MULTIPROC_DIR"


@router.get("/metrics", include_in_schema=False)
async def metrics() -> Response:
    try:
        if os.environ.get(MULTIPROC_DIR_VAR):
            # Each worker writes its counts to files in that folder; this reads them all.
            registry = CollectorRegistry()
            multiprocess.MultiProcessCollector(registry)
            body = generate_latest(registry)
        else:
            body = generate_latest()
    except Exception:
        logger.exception("Could not build the metrics page")
        raise HTTPException(status_code=500, detail="Metrics are unavailable.") from None
    return Response(body, media_type=CONTENT_TYPE_LATEST)
