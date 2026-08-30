"""API-facing summary and methodology models for EcoTwin."""

from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import ConfigDict, Field

from .domain import DataSource, DomainModel


class FrozenApiModel(DomainModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True, frozen=True)


class DashboardSummary(FrozenApiModel):
    snapshot_id: str
    snapshot_at: datetime
    data_version: str
    data_mode: DataSource
    active_repository: Literal["local", "bigquery"]
    display_source: DataSource
    resource_count: int = Field(ge=0)
    compute_count: int = Field(ge=0)
    dependency_count: int = Field(ge=0)
    opportunity_count: int = Field(ge=0)
    idle_count: int = Field(ge=0)
    over_provisioned_count: int = Field(ge=0)
    storage_waste_count: int = Field(ge=0)
    estimated_monthly_cost_usd: float = Field(ge=0)
    estimated_monthly_carbon_kgco2e: float = Field(ge=0)
    potential_monthly_savings_usd: float = Field(ge=0)
    potential_monthly_carbon_reduction_kgco2e: float = Field(ge=0)
    pricing_coverage_note: str = Field(min_length=1)
    carbon_coverage_note: str = Field(min_length=1)
    fallback_reason: str | None = None


class MethodologySnapshot(FrozenApiModel):
    snapshot_id: str
    snapshot_at: datetime
    data_version: str
    data_mode: DataSource
    active_repository: Literal["local", "bigquery"]
    display_source: DataSource
    waste_method_version: str
    simulation_method_version: str
    explanation_prompt_version: str
    detector_thresholds: dict[str, float | int]
    simulation_assumptions: tuple[str, ...]
    explanation_guardrails: tuple[str, ...]
    fallback_reason: str | None = None
