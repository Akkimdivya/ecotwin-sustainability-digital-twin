"""Explainable waste-finding contracts for the Checkpoint 2 rule engine."""

from __future__ import annotations

from datetime import datetime
from typing import Any, Literal

from pydantic import ConfigDict, Field

from .domain import DomainModel

WasteType = Literal["idle_compute", "over_provisioned_compute", "storage_waste"]
Confidence = Literal["HIGH", "MEDIUM", "LOW"]
Severity = Literal["HIGH", "MEDIUM", "LOW"]


class FrozenWasteModel(DomainModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True, frozen=True)


class DetectorThresholds(FrozenWasteModel):
    minimum_sample_days: int = Field(default=7, ge=1)
    idle_cpu_mean_below_pct: float = Field(default=5, ge=0, le=100)
    idle_cpu_p95_below_pct: float = Field(default=10, ge=0, le=100)
    idle_network_below_gb_day: float = Field(default=0.25, ge=0)
    overprovisioned_cpu_p95_below_pct: float = Field(default=40, ge=0, le=100)
    overprovisioned_memory_p95_below_pct: float = Field(default=60, ge=0, le=100)
    unattached_storage_minimum_days: int = Field(default=7, ge=1)


class WasteFinding(FrozenWasteModel):
    finding_id: str
    detector_id: str
    resource_id: str
    resource_name: str
    waste_type: WasteType
    severity: Severity
    title: str
    reason: str
    evidence_window_start: str | None = None
    evidence_window_end: str | None = None
    evidence: dict[str, Any]
    proposed_action: str
    confidence: Confidence
    limitations: tuple[str, ...]
    simulation_eligible: bool


class WasteSummary(FrozenWasteModel):
    total_findings: int = Field(ge=0)
    idle_compute: int = Field(ge=0)
    over_provisioned_compute: int = Field(ge=0)
    storage_waste: int = Field(ge=0)
    high_confidence: int = Field(ge=0)


class WasteReport(FrozenWasteModel):
    snapshot_id: str
    generated_at: datetime
    method_version: str
    thresholds: DetectorThresholds
    findings: tuple[WasteFinding, ...]
    summary: WasteSummary
