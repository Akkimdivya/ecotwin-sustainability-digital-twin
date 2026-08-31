from __future__ import annotations

import asyncio
from dataclasses import replace
from pathlib import Path

from app.config import Settings
from app.models import ExplanationContent, RightsizeRequest
from app.repositories.local import LocalJsonRepository
from app.services import ExplanationService, build_twin_snapshot, simulate_rightsize

DATA_DIR = Path(__file__).resolve().parents[2] / "data"


def base_settings() -> Settings:
    return Settings(
        app_env="test",
        data_mode="local",
        data_dir=DATA_DIR,
        gcp_project=None,
        bigquery_dataset="ecotwin_demo",
        bigquery_location="us-central1",
        log_level="WARNING",
    )


def simulation_result():
    catalog = LocalJsonRepository(DATA_DIR).load_catalog()
    snapshot = build_twin_snapshot(
        catalog,
        data_mode="CONTROLLED_DEMO",
        active_repository="local",
    )
    return simulate_rightsize(
        catalog,
        snapshot,
        RightsizeRequest(
            resource_id="vm-api-01",
            proposed_vcpu=2,
            proposed_memory_gb=8,
        ),
    )


def test_disabled_gemini_returns_number_preserving_fallback() -> None:
    result = simulation_result()
    explanation = asyncio.run(ExplanationService(base_settings()).explain(result))

    assert explanation.provider == "DETERMINISTIC_FALLBACK"
    assert explanation.fallback_reason == "Gemini is disabled by configuration"
    assert "$48.91" in explanation.content.summary
    assert "2.956 kgCO2e" in explanation.content.summary
    assert "HIGH risk" in explanation.content.summary
    assert "81.6%" in explanation.content.rationale
    assert "100.0%" in explanation.content.rationale
    assert len(explanation.content.validation_steps) == 4


def test_vertex_path_validates_structure_and_caches_by_simulation_id() -> None:
    calls = 0

    async def fake_generator(_):
        nonlocal calls
        calls += 1
        return ExplanationContent(
            summary="Structured summary using supplied values.",
            recommendation="Do not apply the high-risk change directly.",
            rationale="The supplied risk reasons require validation.",
            validation_steps=("Run a staging load test.", "Run a monitored canary."),
            rollback_trigger="Rollback on a service-level breach.",
            limitations=("Capacity proxy only.",),
        )

    settings = replace(
        base_settings(),
        gemini_enabled=True,
        gcp_project="test-project",
    )
    service = ExplanationService(settings, generator=fake_generator)
    result = simulation_result()

    async def explain_twice():
        first_result = await service.explain(result)
        second_result = await service.explain(result)
        return first_result, second_result

    first, second = asyncio.run(explain_twice())

    assert first.provider == "VERTEX_AI"
    assert first.model == "gemini-2.5-flash"
    assert not first.cached
    assert second.cached
    assert calls == 1


def test_vertex_failure_retries_once_then_uses_fallback() -> None:
    calls = 0

    async def failing_generator(_):
        nonlocal calls
        calls += 1
        raise RuntimeError("controlled failure")

    settings = replace(
        base_settings(),
        gemini_enabled=True,
        gcp_project="test-project",
    )
    explanation = asyncio.run(
        ExplanationService(settings, generator=failing_generator).explain(simulation_result())
    )

    assert calls == 2
    assert explanation.provider == "DETERMINISTIC_FALLBACK"
    assert explanation.fallback_reason == "RuntimeError"


def test_vertex_response_with_invented_number_uses_fallback() -> None:
    async def invented_number_generator(_):
        return ExplanationContent(
            summary="This scenario saves $999.99 each month.",
            recommendation="Use a monitored canary before any change.",
            rationale="The supplied risk requires careful validation.",
            validation_steps=("Validate the proposed change in staging.", "Monitor a canary."),
            rollback_trigger="Rollback on a service-level breach.",
            limitations=("Capacity proxy only.",),
        )

    settings = replace(
        base_settings(),
        gemini_enabled=True,
        gcp_project="test-project",
    )
    service = ExplanationService(settings, generator=invented_number_generator)
    explanation = asyncio.run(service.explain(simulation_result()))

    assert explanation.provider == "DETERMINISTIC_FALLBACK"
    assert explanation.fallback_reason == "ValueError"
