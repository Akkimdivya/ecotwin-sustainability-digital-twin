"""Build a deterministic, immutable topology snapshot from normalized resources."""

from __future__ import annotations

import hashlib
import json
from collections import Counter, defaultdict
from datetime import date
from statistics import fmean

from app.models import Resource, ResourceCatalog, TelemetryDaily
from app.models.twin import (
    TwinEdge,
    TwinMetricSummary,
    TwinNode,
    TwinNodeState,
    TwinSnapshot,
    TwinSummary,
)

MIN_COMPUTE_SAMPLE_DAYS = 7
LOW_NETWORK_GB_PER_DAY = 0.25
STORAGE_WASTE_DAYS = 7


def _mean(values: list[float]) -> float | None:
    return round(fmean(values), 2) if values else None


def _maximum(values: list[float]) -> float | None:
    return round(max(values), 2) if values else None


def _metric_summary(rows: list[TelemetryDaily]) -> TwinMetricSummary:
    ordered = sorted(rows, key=lambda row: row.date)
    return TwinMetricSummary(
        sample_days=len({row.date for row in ordered}),
        window_start=ordered[0].date.isoformat() if ordered else None,
        window_end=ordered[-1].date.isoformat() if ordered else None,
        cpu_mean_pct=_mean([row.cpu_mean_pct for row in ordered if row.cpu_mean_pct is not None]),
        cpu_p95_pct=_maximum([row.cpu_p95_pct for row in ordered if row.cpu_p95_pct is not None]),
        memory_p95_pct=_maximum(
            [row.memory_p95_pct for row in ordered if row.memory_p95_pct is not None]
        ),
        network_gb_mean=_mean([row.network_gb for row in ordered if row.network_gb is not None]),
        disk_used_pct=_maximum(
            [row.disk_used_pct for row in ordered if row.disk_used_pct is not None]
        ),
    )


def _state_for(
    resource: Resource,
    metrics: TwinMetricSummary,
    snapshot_date: date,
) -> tuple[TwinNodeState, str]:
    if resource.service_type == "persistent_disk" and resource.unattached_since:
        unattached_days = (snapshot_date - resource.unattached_since).days
        if unattached_days >= STORAGE_WASTE_DAYS:
            return "storage_waste", f"Unattached for {unattached_days} days"

    if resource.service_type == "compute_instance":
        if metrics.sample_days < MIN_COMPUTE_SAMPLE_DAYS:
            return "unassessed", "Fewer than 7 complete telemetry days"

        is_idle = (
            metrics.cpu_mean_pct is not None
            and metrics.cpu_mean_pct < 5
            and metrics.cpu_p95_pct is not None
            and metrics.cpu_p95_pct < 10
            and metrics.network_gb_mean is not None
            and metrics.network_gb_mean < LOW_NETWORK_GB_PER_DAY
        )
        if is_idle:
            return "idle", "7-day CPU and network activity are below idle thresholds"

        is_over_provisioned = (
            metrics.cpu_p95_pct is not None
            and metrics.cpu_p95_pct < 40
            and metrics.memory_p95_pct is not None
            and metrics.memory_p95_pct < 60
        )
        if is_over_provisioned:
            return "over_provisioned", "7-day CPU and memory peaks leave substantial headroom"

        return "healthy", "Observed utilization does not meet a waste-state threshold"

    if resource.service_type in {
        "load_balancer",
        "cloud_sql",
        "persistent_disk",
        "storage_bucket",
    }:
        return "healthy", "Resource is attached or serving an observed workload"

    return "unassessed", "No topology state rule is available for this resource type"


def _configuration(resource: Resource) -> dict[str, object]:
    values: dict[str, object] = {}
    for field in ("machine_type", "vcpu", "memory_gb", "storage_gb", "storage_type"):
        value = getattr(resource, field)
        if value is not None:
            values[field] = value
    if resource.attached_to:
        values["attached_to"] = resource.attached_to
    if resource.unattached_since:
        values["unattached_since"] = resource.unattached_since.isoformat()
    return values


def build_twin_snapshot(
    catalog: ResourceCatalog,
    *,
    data_mode: str,
    active_repository: str,
) -> TwinSnapshot:
    """Create one deterministic snapshot; all relationships are validated by the catalog."""

    telemetry_by_resource: defaultdict[str, list[TelemetryDaily]] = defaultdict(list)
    for row in catalog.telemetry:
        telemetry_by_resource[row.resource_id].append(row)

    incoming: Counter[str] = Counter()
    outgoing: Counter[str] = Counter()
    edges: list[TwinEdge] = []
    for dependency in sorted(
        catalog.dependencies,
        key=lambda edge: (edge.source_resource_id, edge.target_resource_id, edge.relationship),
    ):
        incoming[dependency.target_resource_id] += 1
        outgoing[dependency.source_resource_id] += 1
        edges.append(
            TwinEdge(
                id=(
                    f"{dependency.source_resource_id}::{dependency.relationship}::"
                    f"{dependency.target_resource_id}"
                ),
                source=dependency.source_resource_id,
                target=dependency.target_resource_id,
                relationship=dependency.relationship,
            )
        )

    snapshot_at = max(resource.observed_at for resource in catalog.resources)
    nodes: list[TwinNode] = []
    for resource in sorted(catalog.resources, key=lambda item: item.resource_id):
        metrics = _metric_summary(telemetry_by_resource[resource.resource_id])
        state, reason = _state_for(resource, metrics, snapshot_at.date())
        nodes.append(
            TwinNode(
                id=resource.resource_id,
                name=resource.name,
                type=resource.service_type,
                state=state,
                state_reason=reason,
                project_id=resource.project_id,
                region=resource.region,
                zone=resource.zone,
                provider_status=resource.status,
                configuration=_configuration(resource),
                labels=dict(sorted(resource.labels.items())),
                metrics=metrics,
                incoming_count=incoming[resource.resource_id],
                outgoing_count=outgoing[resource.resource_id],
                source=resource.source,
                observed_at=resource.observed_at,
            )
        )

    state_counts = Counter(node.state for node in nodes)
    identity_payload = {
        "data_version": catalog.data_version,
        "snapshot_at": snapshot_at.isoformat(),
        "nodes": [node.model_dump(mode="json") for node in nodes],
        "edges": [edge.model_dump(mode="json") for edge in edges],
    }
    snapshot_id = hashlib.sha256(
        json.dumps(identity_payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
    ).hexdigest()[:16]

    return TwinSnapshot(
        snapshot_id=f"twin-{snapshot_id}",
        snapshot_at=snapshot_at,
        data_version=catalog.data_version,
        data_mode=data_mode,
        active_repository=active_repository,
        nodes=tuple(nodes),
        edges=tuple(edges),
        summary=TwinSummary(
            total_nodes=len(nodes),
            total_edges=len(edges),
            healthy=state_counts["healthy"],
            idle=state_counts["idle"],
            over_provisioned=state_counts["over_provisioned"],
            storage_waste=state_counts["storage_waste"],
            unassessed=state_counts["unassessed"],
        ),
    )
