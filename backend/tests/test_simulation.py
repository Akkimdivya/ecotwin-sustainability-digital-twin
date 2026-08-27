from __future__ import annotations

from pathlib import Path

import pytest
from app.models import RightsizeRequest
from app.repositories.local import LocalJsonRepository
from app.services import SimulationValidationError, build_twin_snapshot, simulate_rightsize

DATA_DIR = Path(__file__).resolve().parents[2] / "data"


def setup_scenario():
    catalog = LocalJsonRepository(DATA_DIR).load_catalog()
    snapshot = build_twin_snapshot(
        catalog,
        data_mode="CONTROLLED_DEMO",
        active_repository="local",
    )
    request = RightsizeRequest(
        resource_id="vm-api-01",
        proposed_vcpu=2,
        proposed_memory_gb=8,
        growth_buffer_pct=20,
    )
    return catalog, snapshot, request


def test_rightsize_simulation_is_deterministic_and_auditable() -> None:
    catalog, snapshot, request = setup_scenario()

    first = simulate_rightsize(catalog, snapshot, request)
    second = simulate_rightsize(catalog, snapshot, request)

    assert first == second
    assert first.simulation_id == "sim-6db42a0b799b9c24"
    assert first.method_version == "simulation-v1.0"
    assert first.snapshot_id == snapshot.snapshot_id
    assert first.before.monthly_cost_usd == 102.82
    assert first.after.monthly_cost_usd == 53.91
    assert first.impact.monthly_cost_savings_usd == 48.91
    assert first.impact.monthly_cost_savings_pct == 47.6
    assert first.impact.carbon_reduction_kgco2e == pytest.approx(2.956)
    assert first.impact.carbon_reduction_pct == 30.8
    assert first.before.attached_storage_cost_usd == first.after.attached_storage_cost_usd
    assert len(first.sources) == 4


def test_rightsize_projection_surfaces_performance_risk() -> None:
    catalog, snapshot, request = setup_scenario()
    result = simulate_rightsize(catalog, snapshot, request)

    assert result.performance.current_cpu_p95_pct == 34
    assert result.performance.predicted_cpu_p95_pct == 81.6
    assert result.performance.predicted_memory_p95_pct == 100
    assert result.risk.level == "HIGH"
    assert result.risk.score == 100
    assert result.confidence == "MEDIUM"
    assert any("CPU p95" in reason for reason in result.risk.reasons)
    assert any("criticality" in reason for reason in result.risk.reasons)


def test_simulation_rejects_unsupported_or_non_reducing_requests() -> None:
    catalog, snapshot, _ = setup_scenario()

    with pytest.raises(SimulationValidationError, match="smaller"):
        simulate_rightsize(
            catalog,
            snapshot,
            RightsizeRequest(
                resource_id="vm-api-01",
                proposed_vcpu=4,
                proposed_memory_gb=16,
            ),
        )

    with pytest.raises(SimulationValidationError, match="price card"):
        simulate_rightsize(
            catalog,
            snapshot,
            RightsizeRequest(
                resource_id="vm-api-01",
                proposed_vcpu=3,
                proposed_memory_gb=12,
            ),
        )

    with pytest.raises(SimulationValidationError, match="requires 8 GB"):
        simulate_rightsize(
            catalog,
            snapshot,
            RightsizeRequest(
                resource_id="vm-api-01",
                proposed_vcpu=2,
                proposed_memory_gb=10,
            ),
        )
