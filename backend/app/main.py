"""EcoTwin FastAPI entry point."""

from __future__ import annotations

import logging
from contextlib import asynccontextmanager
from pathlib import Path
from time import perf_counter
from typing import Any, Literal, cast
from uuid import uuid4

from fastapi import FastAPI, HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from starlette.responses import Response

from app.config import Settings
from app.models import (
    DashboardSummary,
    DataStatus,
    MethodologySnapshot,
    RightsizeRequest,
    RightsizeResult,
    SimulationExplanation,
    TwinNodeDetail,
    TwinSnapshot,
    WasteFinding,
    WasteReport,
)
from app.models.domain import DataSource
from app.repositories import RepositorySelection, select_repository
from app.repositories.simulation_store import (
    BigQuerySimulationStore,
    MemorySimulationStore,
    SimulationStore,
)
from app.services import (
    ExplanationService,
    SimulationValidationError,
    build_dashboard_summary,
    build_methodology_snapshot,
    build_twin_snapshot,
    detect_waste,
    simulate_rightsize,
)


def _configure_logging(level: str) -> None:
    logging.basicConfig(
        level=getattr(logging, level, logging.INFO),
        format="%(asctime)s %(levelname)s %(name)s %(message)s",
    )


def create_app(settings: Settings | None = None) -> FastAPI:
    resolved_settings = settings or Settings.from_env()
    _configure_logging(resolved_settings.log_level)
    request_logger = logging.getLogger("ecotwin.requests")
    bootstrap_logger = logging.getLogger("ecotwin.bootstrap")
    frontend_dir = Path(__file__).resolve().parents[2] / "frontend"

    def display_source_for(current: RepositorySelection) -> DataSource:
        return (
            "CONTROLLED_DEMO"
            if current.active_mode == "bigquery" or current.fallback_reason is None
            else "LOCAL_DEMO_FALLBACK"
        )

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        current = select_repository(resolved_settings)
        app.state.selection = current
        snapshot = build_twin_snapshot(
            current.catalog,
            data_mode=display_source_for(current),
            active_repository=current.active_mode,
        )
        app.state.twin_snapshot = snapshot
        waste_report = detect_waste(snapshot)
        app.state.waste_report = waste_report
        app.state.dashboard_summary = build_dashboard_summary(
            current.catalog,
            snapshot,
            waste_report,
            display_source=display_source_for(current),
            active_repository=cast(Literal["local", "bigquery"], current.active_mode),
            fallback_reason=current.fallback_reason,
        )
        app.state.methodology_snapshot = build_methodology_snapshot(
            snapshot,
            waste_report,
            display_source=display_source_for(current),
            active_repository=cast(Literal["local", "bigquery"], current.active_mode),
            fallback_reason=current.fallback_reason,
        )
        app.state.simulation_store = (
            BigQuerySimulationStore(
                resolved_settings.gcp_project,
                resolved_settings.bigquery_dataset,
                resolved_settings.bigquery_location,
            )
            if current.active_mode == "bigquery" and resolved_settings.gcp_project
            else MemorySimulationStore()
        )
        app.state.explanation_service = ExplanationService(resolved_settings)
        bootstrap_logger.info(
            "loaded_repository active_mode=%s display_source=%s "
            "snapshot_id=%s resources=%s edges=%s",
            current.active_mode,
            display_source_for(current),
            snapshot.snapshot_id,
            len(snapshot.nodes),
            len(snapshot.edges),
        )
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

    if frontend_dir.is_dir():
        app.mount("/assets", StaticFiles(directory=frontend_dir), name="frontend-assets")

    @app.middleware("http")
    async def request_logging(request: Request, call_next) -> Response:
        request_id = request.headers.get("X-Request-ID") or uuid4().hex[:12]
        request.state.request_id = request_id
        started = perf_counter()
        try:
            response = await call_next(request)
        except Exception:
            duration_ms = int((perf_counter() - started) * 1000)
            request_logger.exception(
                "request_failed method=%s path=%s request_id=%s duration_ms=%s",
                request.method,
                request.url.path,
                request_id,
                duration_ms,
            )
            raise
        duration_ms = int((perf_counter() - started) * 1000)
        response.headers["X-Request-ID"] = request_id
        request_logger.info(
            "request_completed method=%s path=%s status=%s request_id=%s duration_ms=%s",
            request.method,
            request.url.path,
            response.status_code,
            request_id,
            duration_ms,
        )
        return response

    def request_id(request: Request) -> str:
        value = getattr(request.state, "request_id", None)
        return value or "unknown"

    @app.exception_handler(Exception)
    async def unhandled_error(request: Request, exc: Exception) -> JSONResponse:
        rid = request_id(request)
        logging.getLogger("ecotwin.errors").exception("Unhandled request error", exc_info=exc)
        return JSONResponse(
            status_code=500,
            content={"detail": "Internal error", "request_id": rid},
            headers={"X-Request-ID": rid},
        )

    @app.exception_handler(HTTPException)
    async def http_error(request: Request, exc: HTTPException) -> JSONResponse:
        rid = request_id(request)
        return JSONResponse(
            status_code=exc.status_code,
            content={"detail": exc.detail, "request_id": rid},
            headers={"X-Request-ID": rid},
        )

    @app.exception_handler(RequestValidationError)
    async def validation_error(request: Request, exc: RequestValidationError) -> JSONResponse:
        rid = request_id(request)
        logging.getLogger("ecotwin.validation").warning(
            "validation_failed path=%s request_id=%s errors=%s",
            request.url.path,
            rid,
            exc.errors(),
        )
        return JSONResponse(
            status_code=422,
            content={"detail": "Validation failed", "request_id": rid},
            headers={"X-Request-ID": rid},
        )

    def selection(request: Request) -> RepositorySelection:
        return request.app.state.selection

    def twin_snapshot(request: Request) -> TwinSnapshot:
        return request.app.state.twin_snapshot

    def waste_report(request: Request) -> WasteReport:
        return request.app.state.waste_report

    def explanation_service(request: Request) -> ExplanationService:
        return request.app.state.explanation_service

    def simulation_store(request: Request) -> SimulationStore:
        return request.app.state.simulation_store

    def persist_simulation(
        request: Request,
        payload: RightsizeRequest,
        result: RightsizeResult,
    ) -> RightsizeResult:
        simulation_store(request).save(payload, result)
        return result

    def require_simulation(request: Request, simulation_id: str) -> RightsizeResult:
        result = simulation_store(request).get(simulation_id)
        if result is None:
            raise HTTPException(status_code=404, detail="Simulation not found")
        return result

    @app.get("/", include_in_schema=False)
    def root():
        index = frontend_dir / "index.html"
        if index.is_file():
            return FileResponse(index)
        return {
            "name": "EcoTwin API",
            "message": "Simulation only - no production changes",
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
        return DataStatus(
            requested_mode=resolved_settings.data_mode,
            active_mode=cast(Literal["local", "bigquery"], current.active_mode),
            display_source=display_source_for(current),
            data_version=current.catalog.data_version,
            resource_count=len(current.catalog.resources),
            fallback_reason=current.fallback_reason,
        )

    @app.get("/api/summary", response_model=DashboardSummary, tags=["overview"])
    def summary(request: Request) -> DashboardSummary:
        return request.app.state.dashboard_summary

    @app.get("/api/resources", tags=["data"])
    def resources(request: Request):
        return selection(request).catalog.resources

    @app.get("/api/telemetry", tags=["data"])
    def telemetry(request: Request, resource_id: str | None = None):
        rows = selection(request).catalog.telemetry
        if resource_id is None:
            return rows
        return [row for row in rows if row.resource_id == resource_id]

    @app.get("/api/dependencies", tags=["data"])
    def dependencies(request: Request):
        return selection(request).catalog.dependencies

    @app.get("/api/price-cards", tags=["data"])
    def price_cards(request: Request):
        return selection(request).catalog.price_cards

    @app.get("/api/carbon-factors", tags=["data"])
    def carbon_factors(request: Request):
        return selection(request).catalog.carbon_factors

    @app.get("/api/twin", response_model=TwinSnapshot, tags=["digital twin"])
    def digital_twin(request: Request) -> TwinSnapshot:
        """Return the immutable topology snapshot used throughout a simulation flow."""

        return twin_snapshot(request)

    @app.get(
        "/api/twin/nodes/{resource_id}",
        response_model=TwinNodeDetail,
        tags=["digital twin"],
    )
    def twin_node(resource_id: str, request: Request) -> TwinNodeDetail:
        snapshot = twin_snapshot(request)
        node = next(
            (candidate for candidate in snapshot.nodes if candidate.id == resource_id),
            None,
        )
        if node is None:
            raise HTTPException(status_code=404, detail="Twin node not found")
        return TwinNodeDetail(
            snapshot_id=snapshot.snapshot_id,
            node=node,
            incoming_edges=tuple(edge for edge in snapshot.edges if edge.target == resource_id),
            outgoing_edges=tuple(edge for edge in snapshot.edges if edge.source == resource_id),
        )

    @app.get("/api/findings", response_model=WasteReport, tags=["waste detection"])
    def waste_findings(request: Request) -> WasteReport:
        return waste_report(request)

    @app.get("/api/opportunities", response_model=WasteReport, tags=["waste detection"])
    def waste_opportunities(request: Request) -> WasteReport:
        return waste_report(request)

    @app.get(
        "/api/findings/{finding_id}",
        response_model=WasteFinding,
        tags=["waste detection"],
    )
    def waste_finding(finding_id: str, request: Request) -> WasteFinding:
        finding = next(
            (
                candidate
                for candidate in waste_report(request).findings
                if candidate.finding_id == finding_id
            ),
            None,
        )
        if finding is None:
            raise HTTPException(status_code=404, detail="Waste finding not found")
        return finding

    @app.post(
        "/api/simulations",
        response_model=RightsizeResult,
        tags=["what-if simulation"],
    )
    def run_simulation(payload: RightsizeRequest, request: Request) -> RightsizeResult:
        """Calculate a read-only scenario; no Google Cloud resource is mutated."""

        rid = request_id(request)
        simulation_logger = logging.getLogger("ecotwin.simulation")
        simulation_logger.info(
            "simulation_requested request_id=%s resource_id=%s "
            "proposed_vcpu=%s proposed_memory_gb=%s growth_buffer_pct=%s",
            rid,
            payload.resource_id,
            payload.proposed_vcpu,
            payload.proposed_memory_gb,
            payload.growth_buffer_pct,
        )
        try:
            result = simulate_rightsize(
                selection(request).catalog,
                twin_snapshot(request),
                payload,
            )
        except SimulationValidationError as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc
        stored = persist_simulation(request, payload, result)
        simulation_logger.info(
            "simulation_completed request_id=%s simulation_id=%s "
            "risk=%s savings_usd=%s carbon_reduction_kgco2e=%s",
            rid,
            stored.simulation_id,
            stored.risk.level,
            stored.impact.monthly_cost_savings_usd,
            stored.impact.carbon_reduction_kgco2e,
        )
        return stored

    @app.get(
        "/api/simulations/{simulation_id}",
        response_model=RightsizeResult,
        tags=["what-if simulation"],
    )
    def get_simulation(simulation_id: str, request: Request) -> RightsizeResult:
        return require_simulation(request, simulation_id)

    @app.post(
        "/api/simulations/{simulation_id}/explain",
        response_model=SimulationExplanation,
        tags=["Gemini explanation"],
    )
    async def explain_simulation_by_id(
        simulation_id: str,
        request: Request,
    ) -> SimulationExplanation:
        result = require_simulation(request, simulation_id)
        rid = request_id(request)
        explanation = await explanation_service(request).explain(result)
        logging.getLogger("ecotwin.explanation").info(
            "explanation_completed request_id=%s simulation_id=%s provider=%s model=%s",
            rid,
            simulation_id,
            explanation.provider,
            explanation.model,
        )
        return explanation

    @app.get("/api/ai-status", tags=["Gemini explanation"])
    def ai_status() -> dict[str, Any]:
        return {
            "enabled": resolved_settings.gemini_enabled,
            "mode": "VERTEX_AI" if resolved_settings.gemini_enabled else "FALLBACK_READY",
            "model": resolved_settings.gemini_model,
            "location": resolved_settings.gemini_location,
            "authentication": "APPLICATION_DEFAULT_CREDENTIALS",
            "api_key_required": False,
        }

    @app.post(
        "/api/explanations",
        response_model=SimulationExplanation,
        tags=["Gemini explanation"],
    )
    async def explain_simulation(
        payload: RightsizeRequest,
        request: Request,
    ) -> SimulationExplanation:
        rid = request_id(request)
        try:
            result = simulate_rightsize(
                selection(request).catalog,
                twin_snapshot(request),
                payload,
            )
        except SimulationValidationError as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc
        stored = persist_simulation(request, payload, result)
        explanation = await explanation_service(request).explain(stored)
        logging.getLogger("ecotwin.explanation").info(
            "explanation_completed request_id=%s simulation_id=%s provider=%s model=%s",
            rid,
            stored.simulation_id,
            explanation.provider,
            explanation.model,
        )
        return explanation

    @app.get("/api/methodology", response_model=MethodologySnapshot, tags=["overview"])
    def methodology(request: Request) -> MethodologySnapshot:
        return request.app.state.methodology_snapshot

    return app


app = create_app()
