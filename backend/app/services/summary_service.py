"""Dashboard summary and methodology snapshots for the EcoTwin API."""

from __future__ import annotations

from typing import Literal

from app.models import (
    DashboardSummary,
    MethodologySnapshot,
    Resource,
    ResourceCatalog,
    TwinNode,
    TwinSnapshot,
    WasteReport,
)
from app.models.domain import DataSource
from app.models.simulation import RightsizeRequest
from app.services.simulation_engine import (
    CPU_DYNAMIC_KW_PER_VCPU,
    CPU_IDLE_KW_PER_VCPU,
    MEMORY_KW_PER_GB,
    SimulationValidationError,
    simulate_rightsize,
)


def _price_card_for(resource: Resource, catalog: ResourceCatalog):
    if resource.service_type == "compute_instance" and resource.machine_type:
        sku_key = f"compute-{resource.machine_type}"
    elif resource.service_type in {"persistent_disk", "storage_bucket"} and resource.storage_type:
        sku_key = f"storage-{resource.storage_type}"
    else:
        return None
    return next(
        (
            candidate
            for candidate in catalog.price_cards
            if candidate.sku_key == sku_key and candidate.region == resource.region
        ),
        None,
    )


def _resource_monthly_cost(resource: Resource, catalog: ResourceCatalog) -> float | None:
    card = _price_card_for(resource, catalog)
    if card is None:
        return None
    if card.unit == "instance_hour":
        return round(card.unit_price_usd * 730, 2)
    if card.unit == "gb_month" and resource.storage_gb is not None:
        return round(card.unit_price_usd * resource.storage_gb, 2)
    return None


def _compute_monthly_carbon(
    node: TwinNode,
    catalog: ResourceCatalog,
) -> float | None:
    if node.type != "compute_instance":
        return None
    factor = next(
        (candidate for candidate in catalog.carbon_factors if candidate.region == node.region),
        None,
    )
    if factor is None:
        return None
    if (
        node.configuration.get("vcpu") is None
        or node.configuration.get("memory_gb") is None
        or node.metrics.cpu_mean_pct is None
    ):
        return None
    vcpu = float(node.configuration["vcpu"])
    memory_gb = float(node.configuration["memory_gb"])
    cpu_mean_pct = float(node.metrics.cpu_mean_pct)
    power_kw = (
        vcpu * (CPU_IDLE_KW_PER_VCPU + CPU_DYNAMIC_KW_PER_VCPU * (cpu_mean_pct / 100))
        + memory_gb * MEMORY_KW_PER_GB
    )
    kwh = power_kw * 730 * factor.pue
    carbon = kwh * factor.gco2e_per_kwh / 1000
    return round(carbon, 3)


def _summed_potential_savings(
    catalog: ResourceCatalog,
    snapshot: TwinSnapshot,
    report: WasteReport,
) -> tuple[float, float]:
    savings_usd = 0.0
    carbon_reduction = 0.0
    nodes_by_id = {node.id: node for node in snapshot.nodes}
    resources_by_id = {resource.resource_id: resource for resource in catalog.resources}

    for finding in report.findings:
        resource = resources_by_id.get(finding.resource_id)
        node = nodes_by_id.get(finding.resource_id)
        if resource is None or node is None:
            continue

        if finding.waste_type == "idle_compute":
            monthly_cost = _resource_monthly_cost(resource, catalog)
            carbon = _compute_monthly_carbon(node, catalog)
            if monthly_cost is not None:
                savings_usd += monthly_cost
            if carbon is not None:
                carbon_reduction += carbon
            continue

        if finding.waste_type == "storage_waste":
            monthly_cost = _resource_monthly_cost(resource, catalog)
            if monthly_cost is not None:
                savings_usd += monthly_cost
            continue

        if finding.waste_type == "over_provisioned_compute":
            current_vcpu = int(resource.vcpu or 0)
            current_memory = float(resource.memory_gb or 0)
            target_vcpu = max(1, current_vcpu // 2)
            target_memory = target_vcpu * 4
            if target_vcpu >= current_vcpu or target_memory > current_memory:
                continue
            try:
                projected = simulate_rightsize(
                    catalog,
                    snapshot,
                    RightsizeRequest(
                        resource_id=resource.resource_id,
                        proposed_vcpu=target_vcpu,
                        proposed_memory_gb=target_memory,
                    ),
                )
            except SimulationValidationError:
                continue
            savings_usd += projected.impact.monthly_cost_savings_usd
            carbon_reduction += projected.impact.carbon_reduction_kgco2e

    return round(savings_usd, 2), round(carbon_reduction, 3)


def build_dashboard_summary(
    catalog: ResourceCatalog,
    snapshot: TwinSnapshot,
    report: WasteReport,
    *,
    display_source: DataSource,
    active_repository: Literal["local", "bigquery"],
    fallback_reason: str | None,
) -> DashboardSummary:
    resource_costs = []
    priced_resources = 0
    unsupported_cost_resources: list[str] = []
    for resource in catalog.resources:
        monthly_cost = _resource_monthly_cost(resource, catalog)
        if monthly_cost is None:
            unsupported_cost_resources.append(resource.resource_id)
            continue
        priced_resources += 1
        resource_costs.append(monthly_cost)

    estimated_monthly_cost = round(sum(resource_costs), 2)
    estimated_monthly_carbon = round(
        sum(
            carbon
            for carbon in (
                _compute_monthly_carbon(node, catalog)
                for node in snapshot.nodes
            )
            if carbon is not None
        ),
        3,
    )
    potential_savings, potential_carbon = _summed_potential_savings(catalog, snapshot, report)
    pricing_note = (
        f"Estimated cost covers {priced_resources} priced resources; "
        f"{len(unsupported_cost_resources)} resources lack a controlled price card."
    )
    carbon_note = (
        "Operational carbon covers compute instances only; non-compute services are excluded "
        "from the estimate."
    )

    return DashboardSummary(
        snapshot_id=snapshot.snapshot_id,
        snapshot_at=snapshot.snapshot_at,
        data_version=catalog.data_version,
        data_mode=snapshot.data_mode,
        active_repository=active_repository,
        display_source=display_source,
        resource_count=len(catalog.resources),
        compute_count=sum(
            resource.service_type == "compute_instance" for resource in catalog.resources
        ),
        dependency_count=len(catalog.dependencies),
        opportunity_count=report.summary.total_findings,
        idle_count=report.summary.idle_compute,
        over_provisioned_count=report.summary.over_provisioned_compute,
        storage_waste_count=report.summary.storage_waste,
        estimated_monthly_cost_usd=estimated_monthly_cost,
        estimated_monthly_carbon_kgco2e=estimated_monthly_carbon,
        potential_monthly_savings_usd=potential_savings,
        potential_monthly_carbon_reduction_kgco2e=potential_carbon,
        pricing_coverage_note=pricing_note,
        carbon_coverage_note=carbon_note,
        fallback_reason=fallback_reason,
    )


def build_methodology_snapshot(
    snapshot: TwinSnapshot,
    report: WasteReport,
    *,
    display_source: DataSource,
    active_repository: Literal["local", "bigquery"],
    fallback_reason: str | None,
) -> MethodologySnapshot:
    return MethodologySnapshot(
        snapshot_id=snapshot.snapshot_id,
        snapshot_at=snapshot.snapshot_at,
        data_version=snapshot.data_version,
        data_mode=snapshot.data_mode,
        active_repository=active_repository,
        display_source=display_source,
        waste_method_version=report.method_version,
        simulation_method_version="simulation-v1.0",
        explanation_prompt_version="ecotwin-explanation-v1.0",
        detector_thresholds=report.thresholds.model_dump(mode="json"),
        simulation_assumptions=(
            "Computed scenarios use versioned price cards rather than live invoices.",
            (
                "Estimated operational carbon is based on transparent power coefficients and "
                "regional factors."
            ),
            "Performance projections are capacity proxies, not load tests.",
        ),
        explanation_guardrails=(
            "Gemini explains only the supplied simulation JSON.",
            "Fallback explanations preserve all numbers exactly.",
            "No production action is performed by the prototype.",
        ),
        fallback_reason=fallback_reason,
    )
