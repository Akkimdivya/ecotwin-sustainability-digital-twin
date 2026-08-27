"""EcoTwin FastAPI entry point."""

from __future__ import annotations

import logging
from contextlib import asynccontextmanager
from typing import Any

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from app.config import Settings
from app.models import DataStatus
from app.repositories import RepositorySelection, select_repository


def _configure_logging(level: str) -> None:
    logging.basicConfig(
        level=getattr(logging, level, logging.INFO),
        format="%(asctime)s %(levelname)s %(name)s %(message)s",
    )


def create_app(settings: Settings | None = None) -> FastAPI:
    resolved_settings = settings or Settings.from_env()
    _configure_logging(resolved_settings.log_level)

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        app.state.selection = select_repository(resolved_settings)
        yield

    app = FastAPI(
        title="EcoTwin API",
        version="0.1.0",
        description=(
            "Read-only sustainability digital-twin API. Checkpoint 2 operates on "
            "clearly labeled controlled data and never mutates cloud infrastructure."
        ),
        lifespan=lifespan,
    )

    @app.exception_handler(Exception)
    async def unhandled_error(_: Request, exc: Exception) -> JSONResponse:
        logging.getLogger("ecotwin.errors").exception("Unhandled request error", exc_info=exc)
        return JSONResponse(status_code=500, content={"detail": "Internal error"})

    def selection(request: Request) -> RepositorySelection:
        return request.app.state.selection

    @app.get("/", tags=["system"])
    def root() -> dict[str, str]:
        return {
            "name": "EcoTwin API",
            "message": "Simulation only — no production changes",
            "docs": "/docs",
        }

    @app.get("/api/health", tags=["system"])
    def health(request: Request) -> dict[str, Any]:
        current = selection(request)
        return {
            "status": "ok",
            "service": "ecotwin-api",
            "version": app.version,
            "data_mode": current.active_mode,
        }

    @app.get("/api/data-status", response_model=DataStatus, tags=["data"])
    def data_status(request: Request) -> DataStatus:
        current = selection(request)
        display_source = (
            "CONTROLLED_DEMO"
            if current.active_mode == "bigquery" or current.fallback_reason is None
            else "LOCAL_DEMO_FALLBACK"
        )
        return DataStatus(
            requested_mode=resolved_settings.data_mode,
            active_mode=current.active_mode,  # type: ignore[arg-type]
            display_source=display_source,
            data_version=current.catalog.data_version,
            resource_count=len(current.catalog.resources),
            fallback_reason=current.fallback_reason,
        )

    @app.get("/api/resources", tags=["data"])
    def resources(request: Request):
        return selection(request).catalog.resources

    @app.get("/api/telemetry", tags=["data"])
    def telemetry(request: Request, resource_id: str | None = None):
        rows = selection(request).catalog.telemetry
        return (
            rows if resource_id is None else [row for row in rows if row.resource_id == resource_id]
        )

    @app.get("/api/dependencies", tags=["data"])
    def dependencies(request: Request):
        return selection(request).catalog.dependencies

    @app.get("/api/price-cards", tags=["data"])
    def price_cards(request: Request):
        return selection(request).catalog.price_cards

    @app.get("/api/carbon-factors", tags=["data"])
    def carbon_factors(request: Request):
        return selection(request).catalog.carbon_factors

    return app


app = create_app()
