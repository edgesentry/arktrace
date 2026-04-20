"""Pipeline API server.

Exposes endpoints consumed by the arktrace SPA and its CF Worker infrastructure.

Start with:
    uv run uvicorn pipeline.src.api.main:app --host 0.0.0.0 --port 8000 --reload

Environment variables:
    PIPELINE_SECRET   Shared secret checked by POST /api/reviews/merge.
                      Set the same value as the PIPELINE_SECRET Worker secret.
    DB_PATH           Path to the DuckDB file (default: data/processed/singapore.duckdb).
"""

from __future__ import annotations

from fastapi import FastAPI

from pipeline.src.api.routes.reviews import router as reviews_router


def create_app() -> FastAPI:
    app = FastAPI(title="arktrace pipeline API", version="0.1.0", docs_url="/api/docs")
    app.include_router(reviews_router)
    return app


app = create_app()
