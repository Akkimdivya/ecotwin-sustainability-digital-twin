from __future__ import annotations

from pathlib import Path

from app.models.twin import TwinMetricSummary
from app.models.waste import DetectorThresholds
from app.repositories.local import LocalJsonRepository
from app.services import build_twin_snapshot, detect_waste
from app.services.waste_detection import is_idle_compute, is_over_provisioned_compute

DATA_DIR = Path(__file__).resolve().parents[2] / "data"
RULES = DetectorThresholds()


def compute_metrics(
    *,
    cpu_mean: float,
    cpu_p95: float,
    memory_p95: float,
    network: float,
) -> TwinMetricSummary:
    return TwinMetricSummary(
        sample_days=7,
        window_start="2026-08-20",
        window_end="2026-08-26",
        cpu_mean_pct=cpu_mean,
        cpu_p95_pct=cpu_p95,
        memory_p95_pct=memory_p95,
        network_gb_mean=network,
    )


def test_idle_detector_uses_strict_5_and_10_percent_boundaries() -> None:
    assert is_idle_compute(
        compute_metrics(cpu_mean=4.9, cpu_p95=9.9, memory_p95=20, network=0.24), RULES
    )
    assert not is_idle_compute(
        compute_metrics(cpu_mean=5, cpu_p95=9.9, memory_p95=20, network=0.24), RULES
    )
    assert not is_idle_compute(
        compute_metrics(cpu_mean=4.9, cpu_p95=10, memory_p95=20, network=0.24), RULES
    )


def test_overprovisioned_detector_uses_strict_40_and_60_percent_boundaries() -> None:
    assert is_over_provisioned_compute(
        compute_metrics(cpu_mean=15, cpu_p95=39.9, memory_p95=59.9, network=2), RULES
    )
    assert not is_over_provisioned_compute(
        compute_metrics(cpu_mean=15, cpu_p95=40, memory_p95=59.9, network=2), RULES
    )
    assert not is_over_provisioned_compute(
        compute_metrics(cpu_mean=15, cpu_p95=39.9, memory_p95=60, network=2), RULES
    )


def test_controlled_catalog_produces_three_explainable_findings() -> None:
    catalog = LocalJsonRepository(DATA_DIR).load_catalog()
    snapshot = build_twin_snapshot(
        catalog,
        data_mode="CONTROLLED_DEMO",
        active_repository="local",
    )
    report = detect_waste(snapshot)

    assert report.summary.total_findings == 3
    assert report.summary.idle_compute == 1
    assert report.summary.over_provisioned_compute == 1
    assert report.summary.storage_waste == 1
    assert report.summary.high_confidence == 3
    assert {finding.resource_id for finding in report.findings} == {
        "vm-api-01",
        "vm-batch-02",
        "disk-orphan-01",
    }
    assert all(finding.reason for finding in report.findings)
    assert all(finding.limitations for finding in report.findings)
    assert all(finding.simulation_eligible for finding in report.findings)
