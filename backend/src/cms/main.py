"""FastAPI app factory.

The project is installed (`uv sync` gives you an editable install), so this is
importable and runnable from any working directory:

    uv run uvicorn cms.main:app --reload
"""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from cms.api.v1.router import api_router
from cms.config.logging_config import setup_logging
from cms.config.settings import get_settings


def create_app() -> FastAPI:
    setup_logging()

    settings = get_settings()
    app = FastAPI(title="Complaint Management System API")

    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins_list,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    app.include_router(api_router)
    return app


app = create_app()
