"""Auditable request and result contracts for deterministic what-if simulations."""

from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import ConfigDict, Field, model_validator

from .domain import DomainModel


class FrozenSimulationModel(DomainModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True, frozen=True)


class RightsizeRequest(DomainModel):
    action: Literal["RIGHTSIZE_VM"] = "RIGHTSIZE_VM"
    resource_id: str = Field(min_length=1)
    proposed_vcpu: int = Field(ge=1, le=128)
    proposed_memory_gb: float = Field(gt=0, le=1024)
    growth_buffer_pct: float = Field(default=20, ge=0, le=100)
    runtime_hours_per_month: float = Field(default=730, gt=0, le=744)


class ScenarioConfiguration(FrozenSimulationModel):
    machine_type: str
    vcpu: int = Field(ge=1)
    memory_gb: float = Field(gt=0)
    compute_cost_usd: float = Field(ge=0)
    attached_storage_cost_usd: float = Field(ge=0)
    monthly_cost_usd: float = Field(ge=0)
    estimated_average_kw: float = Field(ge=0)
    estimated_kwh: float = Field(ge=0)
    estimated_carbon_kgco2e: float = Field(ge=0)


class SimulationImpact(FrozenSimulationModel):
    monthly_cost_delta_usd: float
    monthly_cost_savings_usd: float = Field(ge=0)
    monthly_cost_savings_pct: float = Field(ge=0, le=100)
    carbon_delta_kgco2e: float
    carbon_reduction_kgco2e: float = Field(ge=0)
    carbon_reduction_pct: float = Field(ge=0, le=100)


class PerformanceProjection(FrozenSimulationModel):
    growth_buffer_pct: float = Field(ge=0, le=100)
    current_cpu_mean_pct: float = Field(ge=0, le=100)
    current_cpu_p95_pct: float = Field(ge=0, le=100)
    predicted_cpu_mean_pct: float = Field(ge=0, le=100)
    predicted_cpu_p95_pct: float = Field(ge=0, le=100)
    cpu_headroom_pct: float = Field(ge=0, le=100)
    current_memory_p95_pct: float = Field(ge=0, le=100)
    predicted_memory_p95_pct: float = Field(ge=0, le=100)
    memory_headroom_pct: float = Field(ge=0, le=100)
    sample_days: int = Field(ge=0)


class RiskAssessment(FrozenSimulationModel):
    level: Literal["LOW", "MEDIUM", "HIGH"]
    score: int = Field(ge=0, le=100)
    reasons: tuple[str, ...]


class MethodSource(FrozenSimulationModel):
    name: str
    effective_date: str
    source_url: str
    source_type: str


class RightsizeResult(FrozenSimulationModel):
    simulation_id: str
    action: Literal["RIGHTSIZE_VM"]
    resource_id: str
    resource_name: str
    snapshot_id: str
    calculated_at: datetime
    before: ScenarioConfiguration
    after: ScenarioConfiguration
    impact: SimulationImpact
    performance: PerformanceProjection
    risk: RiskAssessment
    confidence: Literal["HIGH", "MEDIUM", "LOW"]
    confidence_reason: str
    assumptions: tuple[str, ...]
    sources: tuple[MethodSource, ...]
    method_version: str
    data_version: str
    data_mode: str

    @model_validator(mode="after")
    def ensure_savings_match_delta(self) -> RightsizeResult:
        expected = max(0, -self.impact.monthly_cost_delta_usd)
        if abs(expected - self.impact.monthly_cost_savings_usd) > 0.02:
            raise ValueError("monthly savings must agree with the signed cost delta")
        return self
