"""FastAPI app factory.

Run from the `backend/` directory, which is what puts these packages on
`sys.path` and what makes `config.settings` find the relative `.env`:

    uv run uvicorn main:app --reload
"""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from api.v1.router import api_router
from config.logging_config import setup_logging
from config.settings import get_settings


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
