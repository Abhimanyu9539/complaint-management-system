"""FastAPI app factory.

The project is installed (`uv sync` gives you an editable install), so this is
importable and runnable from any working directory:

    uv run uvicorn cms.main:app --reload
"""

import logging

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from cms.api.v1.router import api_router
from cms.config.logging_config import setup_logging
from cms.config.settings import get_settings

logger = logging.getLogger(__name__)


def create_app() -> FastAPI:
    setup_logging()

    settings = get_settings()
    app = FastAPI(title="Complaint Management System API")

    # `allow_origin_regex` covers the dev server, whose port and hostname both
    # move; `allow_origins` carries the deployment's real origins. Starlette ORs
    # the two, so a deployment that sets one and clears the other gets exactly
    # what it configured. See `Settings.cors_origin_regex`.
    origins = settings.cors_origins_list
    origin_regex = settings.cors_origin_regex_or_none
    if not origins and origin_regex is None:
        logger.warning(
            "CORS is configured to allow no origins; browser clients will be "
            "blocked. Set CORS_ORIGINS or CORS_ORIGIN_REGEX."
        )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=origins,
        allow_origin_regex=origin_regex,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    app.include_router(api_router)
    return app


app = create_app()
