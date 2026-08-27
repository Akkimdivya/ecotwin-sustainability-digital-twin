"""Deterministic, auditable compute right-sizing simulation engine."""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass

from app.models import ResourceCatalog
from app.models.simulation import (
    MethodSource,
    PerformanceProjection,
    RightsizeRequest,
    RightsizeResult,
    RiskAssessment,
    ScenarioConfiguration,
    SimulationImpact,
)
from app.models.twin import TwinNode, TwinSnapshot

METHOD_VERSION = "simulation-v1.0"
CPU_IDLE_KW_PER_VCPU = 0.004
CPU_DYNAMIC_KW_PER_VCPU = 0.012
MEMORY_KW_PER_GB = 0.000375


class SimulationValidationError(ValueError):
    """Raised when a requested scenario cannot be supported by known evidence."""


@dataclass(frozen=True, slots=True)
class CostComponents:
    compute: float
    storage: float

    @property
    def total(self) -> float:
        return self.compute + self.storage


def _round_money(value: float) -> float:
    return round(value + 1e-12, 2)


def _round_measure(value: float) -> float:
    return round(value + 1e-12, 3)


def _find_node(snapshot: TwinSnapshot, resource_id: str) -> TwinNode:
    node = next((candidate for candidate in snapshot.nodes if candidate.id == resource_id), None)
    if node is None:
        raise SimulationValidationError("Resource does not exist in this twin snapshot")
    if node.type != "compute_instance":
        raise SimulationValidationError("RIGHTSIZE_VM requires a compute instance")
    return node


def _price_card(catalog: ResourceCatalog, *, machine_type: str, region: str):
    sku_key = f"compute-{machine_type}"
    card = next(
        (
            candidate
            for candidate in catalog.price_cards
            if candidate.sku_key == sku_key and candidate.region == region
        ),
        None,
    )
    if card is None:
        raise SimulationValidationError(
            f"No controlled price card for {machine_type} in {region}"
        )
    return card


def _attached_storage_cost(
    catalog: ResourceCatalog,
    snapshot: TwinSnapshot,
    resource_id: str,
) -> tuple[float, list]:
    disk_ids = {
        edge.source
        for edge in snapshot.edges
        if edge.target == resource_id and edge.relationship == "attached_to"
    }
    price_cards = []
    total = 0.0
    for resource in catalog.resources:
        if resource.resource_id not in disk_ids:
            continue
        sku_key = f"storage-{resource.storage_type}"
        card = next(
            (
                candidate
                for candidate in catalog.price_cards
                if candidate.sku_key == sku_key and candidate.region == resource.region
            ),
            None,
        )
        if card is None or resource.storage_gb is None:
            raise SimulationValidationError(
                f"Missing storage price for attached disk {resource.name}"
            )
        total += resource.storage_gb * card.unit_price_usd
        price_cards.append(card)
    return total, price_cards


def _power_kw(vcpu: int, memory_gb: float, cpu_mean_pct: float) -> float:
    cpu_fraction = cpu_mean_pct / 100
    return (
        vcpu * (CPU_IDLE_KW_PER_VCPU + CPU_DYNAMIC_KW_PER_VCPU * cpu_fraction)
        + memory_gb * MEMORY_KW_PER_GB
    )


def _risk(
    node: TwinNode,
    projection: PerformanceProjection,
) -> RiskAssessment:
    reasons: list[str] = []
    score = 15
    level = "LOW"

    if projection.sample_days < 7:
        level = "HIGH"
        score += 50
        reasons.append("Fewer than seven complete telemetry days")
    if projection.predicted_cpu_p95_pct > 80:
        level = "HIGH"
        score += 35
        reasons.append("Predicted CPU p95 exceeds 80%")
    elif projection.predicted_cpu_p95_pct > 65:
        level = "MEDIUM"
        score += 20
        reasons.append("Predicted CPU p95 exceeds the 65% low-risk boundary")

    if projection.predicted_memory_p95_pct > 90:
        level = "HIGH"
        score += 35
        reasons.append("Predicted memory p95 exceeds 90%")
    elif projection.memory_headroom_pct < 25:
        if level == "LOW":
            level = "MEDIUM"
        score += 20
        reasons.append("Projected memory headroom is below 25%")

    if node.labels.get("criticality") == "high" and node.incoming_count + node.outgoing_count >= 2:
        level = "HIGH"
        score += 20
        reasons.append(
            "The node is labeled high criticality and participates in multiple dependencies"
        )

    if not reasons:
        reasons.append("Projected utilization preserves the configured low-risk headroom")
    return RiskAssessment(level=level, score=min(100, score), reasons=tuple(reasons))


def _confidence(sample_days: int) -> tuple[str, str]:
    if sample_days >= 14:
        return "HIGH", "At least 14 complete telemetry days support the projection."
    if sample_days >= 7:
        return "MEDIUM", "Seven to thirteen telemetry days support a directional estimate."
    return "LOW", "Fewer than seven telemetry days limit the estimate."


def simulate_rightsize(
    catalog: ResourceCatalog,
    snapshot: TwinSnapshot,
    request: RightsizeRequest,
) -> RightsizeResult:
    node = _find_node(snapshot, request.resource_id)
    current_vcpu = int(node.configuration.get("vcpu", 0))
    current_memory = float(node.configuration.get("memory_gb", 0))
    current_machine_type = str(node.configuration.get("machine_type", ""))
    if not current_vcpu or not current_memory or not current_machine_type:
        raise SimulationValidationError("Current compute configuration is incomplete")
    if request.proposed_vcpu >= current_vcpu:
        raise SimulationValidationError("Proposed vCPU must be smaller than the current vCPU")
    if request.proposed_memory_gb > current_memory:
        raise SimulationValidationError("Proposed memory cannot exceed current memory")
    metrics = node.metrics
    if (
        metrics.cpu_mean_pct is None
        or metrics.cpu_p95_pct is None
        or metrics.memory_p95_pct is None
    ):
        raise SimulationValidationError("CPU and memory telemetry are required")

    proposed_machine_type = f"e2-standard-{request.proposed_vcpu}"
    expected_memory_gb = request.proposed_vcpu * 4
    if request.proposed_memory_gb != expected_memory_gb:
        raise SimulationValidationError(
            f"{proposed_machine_type} requires {expected_memory_gb:g} GB memory"
        )
    current_price = _price_card(
        catalog,
        machine_type=current_machine_type,
        region=node.region,
    )
    proposed_price = _price_card(
        catalog,
        machine_type=proposed_machine_type,
        region=node.region,
    )
    storage_cost, storage_cards = _attached_storage_cost(catalog, snapshot, node.id)
    current_cost = CostComponents(
        compute=current_price.unit_price_usd * request.runtime_hours_per_month,
        storage=storage_cost,
    )
    proposed_cost = CostComponents(
        compute=proposed_price.unit_price_usd * request.runtime_hours_per_month,
        storage=storage_cost,
    )

    factor = next(
        (candidate for candidate in catalog.carbon_factors if candidate.region == node.region),
        None,
    )
    if factor is None:
        raise SimulationValidationError(f"No controlled carbon factor for {node.region}")

    growth_multiplier = 1 + request.growth_buffer_pct / 100
    cpu_scale = current_vcpu / request.proposed_vcpu
    memory_scale = current_memory / request.proposed_memory_gb
    predicted_cpu_mean = min(100, metrics.cpu_mean_pct * cpu_scale * growth_multiplier)
    predicted_cpu_p95 = min(100, metrics.cpu_p95_pct * cpu_scale * growth_multiplier)
    predicted_memory_p95 = min(100, metrics.memory_p95_pct * memory_scale * growth_multiplier)
    performance = PerformanceProjection(
        growth_buffer_pct=request.growth_buffer_pct,
        current_cpu_mean_pct=metrics.cpu_mean_pct,
        current_cpu_p95_pct=metrics.cpu_p95_pct,
        predicted_cpu_mean_pct=round(predicted_cpu_mean, 1),
        predicted_cpu_p95_pct=round(predicted_cpu_p95, 1),
        cpu_headroom_pct=round(100 - predicted_cpu_p95, 1),
        current_memory_p95_pct=metrics.memory_p95_pct,
        predicted_memory_p95_pct=round(predicted_memory_p95, 1),
        memory_headroom_pct=round(100 - predicted_memory_p95, 1),
        sample_days=metrics.sample_days,
    )

    current_kw = _power_kw(current_vcpu, current_memory, metrics.cpu_mean_pct)
    proposed_kw = _power_kw(
        request.proposed_vcpu,
        request.proposed_memory_gb,
        predicted_cpu_mean,
    )
    current_kwh = current_kw * request.runtime_hours_per_month * factor.pue
    proposed_kwh = proposed_kw * request.runtime_hours_per_month * factor.pue
    current_carbon = current_kwh * factor.gco2e_per_kwh / 1000
    proposed_carbon = proposed_kwh * factor.gco2e_per_kwh / 1000

    before = ScenarioConfiguration(
        machine_type=current_machine_type,
        vcpu=current_vcpu,
        memory_gb=current_memory,
        compute_cost_usd=_round_money(current_cost.compute),
        attached_storage_cost_usd=_round_money(current_cost.storage),
        monthly_cost_usd=_round_money(current_cost.total),
        estimated_average_kw=_round_measure(current_kw),
        estimated_kwh=_round_measure(current_kwh),
        estimated_carbon_kgco2e=_round_measure(current_carbon),
    )
    after = ScenarioConfiguration(
        machine_type=proposed_machine_type,
        vcpu=request.proposed_vcpu,
        memory_gb=request.proposed_memory_gb,
        compute_cost_usd=_round_money(proposed_cost.compute),
        attached_storage_cost_usd=_round_money(proposed_cost.storage),
        monthly_cost_usd=_round_money(proposed_cost.total),
        estimated_average_kw=_round_measure(proposed_kw),
        estimated_kwh=_round_measure(proposed_kwh),
        estimated_carbon_kgco2e=_round_measure(proposed_carbon),
    )
    cost_delta = after.monthly_cost_usd - before.monthly_cost_usd
    carbon_delta = after.estimated_carbon_kgco2e - before.estimated_carbon_kgco2e
    impact = SimulationImpact(
        monthly_cost_delta_usd=_round_money(cost_delta),
        monthly_cost_savings_usd=_round_money(max(0, -cost_delta)),
        monthly_cost_savings_pct=round(max(0, -cost_delta) / before.monthly_cost_usd * 100, 1),
        carbon_delta_kgco2e=_round_measure(carbon_delta),
        carbon_reduction_kgco2e=_round_measure(max(0, -carbon_delta)),
        carbon_reduction_pct=round(
            max(0, -carbon_delta) / before.estimated_carbon_kgco2e * 100,
            1,
        ),
    )
    risk = _risk(node, performance)
    confidence, confidence_reason = _confidence(metrics.sample_days)

    identity = {
        "snapshot_id": snapshot.snapshot_id,
        "method_version": METHOD_VERSION,
        "request": request.model_dump(mode="json"),
    }
    simulation_id = "sim-" + hashlib.sha256(
        json.dumps(identity, sort_keys=True, separators=(",", ":")).encode("utf-8")
    ).hexdigest()[:16]
    source_cards = [current_price, proposed_price, *storage_cards]
    unique_cards = {card.sku_key: card for card in source_cards}.values()
    sources = tuple(
        MethodSource(
            name=card.sku_key,
            effective_date=card.effective_date.isoformat(),
            source_url=str(card.source_url),
            source_type=card.source_type,
        )
        for card in unique_cards
    ) + (
        MethodSource(
            name=f"carbon-factor-{factor.region}",
            effective_date=factor.effective_date.isoformat(),
            source_url=str(factor.source_url),
            source_type=factor.source_type,
        ),
    )

    return RightsizeResult(
        simulation_id=simulation_id,
        action=request.action,
        resource_id=node.id,
        resource_name=node.name,
        snapshot_id=snapshot.snapshot_id,
        calculated_at=snapshot.snapshot_at,
        before=before,
        after=after,
        impact=impact,
        performance=performance,
        risk=risk,
        confidence=confidence,
        confidence_reason=confidence_reason,
        assumptions=(
            f"{request.runtime_hours_per_month:g} runtime hours per month.",
            f"{request.growth_buffer_pct:g}% utilization growth buffer.",
            "Controlled price cards are scenario assumptions, not invoice forecasts.",
            "Operational-carbon estimate uses CPU and memory power coefficients plus regional PUE.",
            "Performance projection is a capacity proxy, not a load test.",
            "Attached storage remains unchanged in the right-sizing scenario.",
        ),
        sources=sources,
        method_version=METHOD_VERSION,
        data_version=catalog.data_version,
        data_mode=snapshot.data_mode,
    )
