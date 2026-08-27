"""Deterministic waste detectors with explicit, testable thresholds."""

from __future__ import annotations

from collections import Counter
from datetime import date

from app.models.twin import TwinMetricSummary, TwinNode, TwinSnapshot
from app.models.waste import (
    DetectorThresholds,
    WasteFinding,
    WasteReport,
    WasteSummary,
)

METHOD_VERSION = "waste-rules-v1.0"


def is_idle_compute(
    metrics: TwinMetricSummary,
    thresholds: DetectorThresholds,
) -> bool:
    return (
        metrics.sample_days >= thresholds.minimum_sample_days
        and metrics.cpu_mean_pct is not None
        and metrics.cpu_mean_pct < thresholds.idle_cpu_mean_below_pct
        and metrics.cpu_p95_pct is not None
        and metrics.cpu_p95_pct < thresholds.idle_cpu_p95_below_pct
        and metrics.network_gb_mean is not None
        and metrics.network_gb_mean < thresholds.idle_network_below_gb_day
    )


def is_over_provisioned_compute(
    metrics: TwinMetricSummary,
    thresholds: DetectorThresholds,
) -> bool:
    return (
        metrics.sample_days >= thresholds.minimum_sample_days
        and not is_idle_compute(metrics, thresholds)
        and metrics.cpu_p95_pct is not None
        and metrics.cpu_p95_pct < thresholds.overprovisioned_cpu_p95_below_pct
        and metrics.memory_p95_pct is not None
        and metrics.memory_p95_pct < thresholds.overprovisioned_memory_p95_below_pct
    )


def _idle_finding(node: TwinNode, thresholds: DetectorThresholds) -> WasteFinding | None:
    if node.type != "compute_instance" or not is_idle_compute(node.metrics, thresholds):
        return None
    return WasteFinding(
        finding_id=f"idle-compute::{node.id}",
        detector_id="idle-compute-v1",
        resource_id=node.id,
        resource_name=node.name,
        waste_type="idle_compute",
        severity="HIGH",
        title="Idle compute workload",
        reason=(
            "CPU mean, CPU p95 and network activity stayed below all idle thresholds "
            "for seven complete days."
        ),
        evidence_window_start=node.metrics.window_start,
        evidence_window_end=node.metrics.window_end,
        evidence={
            "sample_days": node.metrics.sample_days,
            "cpu_mean_pct": node.metrics.cpu_mean_pct,
            "cpu_p95_pct": node.metrics.cpu_p95_pct,
            "network_gb_mean": node.metrics.network_gb_mean,
            "thresholds": {
                "cpu_mean_below_pct": thresholds.idle_cpu_mean_below_pct,
                "cpu_p95_below_pct": thresholds.idle_cpu_p95_below_pct,
                "network_below_gb_day": thresholds.idle_network_below_gb_day,
            },
        },
        proposed_action="Simulate a scheduled shutdown, then validate ownership and job timing.",
        confidence="HIGH",
        limitations=(
            "Daily aggregates can hide short bursts inside the measurement window.",
            "Confirm the workload schedule and owner before any production action.",
        ),
        simulation_eligible=True,
    )


def _over_provisioned_finding(
    node: TwinNode,
    thresholds: DetectorThresholds,
) -> WasteFinding | None:
    if node.type != "compute_instance" or not is_over_provisioned_compute(
        node.metrics, thresholds
    ):
        return None
    return WasteFinding(
        finding_id=f"over-provisioned-compute::{node.id}",
        detector_id="over-provisioned-compute-v1",
        resource_id=node.id,
        resource_name=node.name,
        waste_type="over_provisioned_compute",
        severity="MEDIUM",
        title="Compute right-sizing candidate",
        reason="Seven-day CPU and memory peaks remain below right-sizing thresholds.",
        evidence_window_start=node.metrics.window_start,
        evidence_window_end=node.metrics.window_end,
        evidence={
            "sample_days": node.metrics.sample_days,
            "cpu_p95_pct": node.metrics.cpu_p95_pct,
            "memory_p95_pct": node.metrics.memory_p95_pct,
            "current_vcpu": node.configuration.get("vcpu"),
            "current_memory_gb": node.configuration.get("memory_gb"),
            "thresholds": {
                "cpu_p95_below_pct": thresholds.overprovisioned_cpu_p95_below_pct,
                "memory_p95_below_pct": thresholds.overprovisioned_memory_p95_below_pct,
            },
        },
        proposed_action="Simulate one machine size smaller with at least 20% projected headroom.",
        confidence="HIGH",
        limitations=(
            "The prototype uses a seven-day controlled window and does not forecast seasonality.",
            "Validate latency and memory pressure with a canary before implementation.",
        ),
        simulation_eligible=True,
    )


def _storage_finding(
    node: TwinNode,
    snapshot_date: date,
    thresholds: DetectorThresholds,
) -> WasteFinding | None:
    if node.type != "persistent_disk" or "unattached_since" not in node.configuration:
        return None
    unattached_since = date.fromisoformat(str(node.configuration["unattached_since"]))
    unattached_days = (snapshot_date - unattached_since).days
    if unattached_days < thresholds.unattached_storage_minimum_days:
        return None
    return WasteFinding(
        finding_id=f"storage-waste::{node.id}",
        detector_id="unattached-storage-v1",
        resource_id=node.id,
        resource_name=node.name,
        waste_type="storage_waste",
        severity="MEDIUM",
        title="Unattached persistent disk",
        reason=f"The disk has been unattached for {unattached_days} days.",
        evidence_window_start=unattached_since.isoformat(),
        evidence_window_end=snapshot_date.isoformat(),
        evidence={
            "unattached_days": unattached_days,
            "storage_gb": node.configuration.get("storage_gb"),
            "storage_type": node.configuration.get("storage_type"),
            "disk_used_pct": node.metrics.disk_used_pct,
            "minimum_unattached_days": thresholds.unattached_storage_minimum_days,
        },
        proposed_action="Simulate deletion after snapshot, backup and ownership validation.",
        confidence="HIGH",
        limitations=(
            "An unattached disk may still be retained intentionally for rollback or compliance.",
            "Confirm backup and retention requirements before deletion.",
        ),
        simulation_eligible=True,
    )


def detect_waste(
    snapshot: TwinSnapshot,
    thresholds: DetectorThresholds | None = None,
) -> WasteReport:
    rules = thresholds or DetectorThresholds()
    findings: list[WasteFinding] = []
    for node in snapshot.nodes:
        for finding in (
            _idle_finding(node, rules),
            _over_provisioned_finding(node, rules),
            _storage_finding(node, snapshot.snapshot_at.date(), rules),
        ):
            if finding is not None:
                findings.append(finding)

    ordered = tuple(sorted(findings, key=lambda item: (item.waste_type, item.resource_id)))
    counts = Counter(finding.waste_type for finding in ordered)
    return WasteReport(
        snapshot_id=snapshot.snapshot_id,
        generated_at=snapshot.snapshot_at,
        method_version=METHOD_VERSION,
        thresholds=rules,
        findings=ordered,
        summary=WasteSummary(
            total_findings=len(ordered),
            idle_compute=counts["idle_compute"],
            over_provisioned_compute=counts["over_provisioned_compute"],
            storage_waste=counts["storage_waste"],
            high_confidence=sum(finding.confidence == "HIGH" for finding in ordered),
        ),
    )
