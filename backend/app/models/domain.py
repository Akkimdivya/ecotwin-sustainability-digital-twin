"""Provider-neutral domain models for the EcoTwin controlled dataset."""

from __future__ import annotations

from datetime import date, datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, HttpUrl, model_validator

DataSource = Literal["CONTROLLED_DEMO", "GCP_CONNECTED", "LOCAL_DEMO_FALLBACK"]
ResourceType = Literal[
    "load_balancer",
    "compute_instance",
    "cloud_sql",
    "persistent_disk",
    "storage_bucket",
]


class DomainModel(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)


class Resource(DomainModel):
    resource_id: str = Field(min_length=1)
    name: str = Field(min_length=1)
    project_id: str = Field(min_length=1)
    service_type: ResourceType
    region: str = Field(min_length=1)
    zone: str | None = None
    machine_type: str | None = None
    vcpu: int | None = Field(default=None, ge=1)
    memory_gb: float | None = Field(default=None, gt=0)
    storage_gb: float | None = Field(default=None, ge=0)
    storage_type: str | None = None
    status: Literal["RUNNING", "STOPPED", "AVAILABLE", "IN_USE"]
    attached_to: str | None = None
    unattached_since: date | None = None
    labels: dict[str, str] = Field(default_factory=dict)
    source: DataSource
    observed_at: datetime

    @model_validator(mode="after")
    def validate_resource_shape(self) -> Resource:
        if self.service_type == "compute_instance" and (
            self.machine_type is None or self.vcpu is None or self.memory_gb is None
        ):
            raise ValueError("compute instances require machine_type, vcpu, and memory_gb")
        if self.service_type == "persistent_disk" and self.storage_gb is None:
            raise ValueError("persistent disks require storage_gb")
        if self.attached_to and self.unattached_since:
            raise ValueError("an attached resource cannot have unattached_since")
        return self


class TelemetryDaily(DomainModel):
    resource_id: str = Field(min_length=1)
    date: date
    cpu_mean_pct: float | None = Field(default=None, ge=0, le=100)
    cpu_p95_pct: float | None = Field(default=None, ge=0, le=100)
    memory_mean_pct: float | None = Field(default=None, ge=0, le=100)
    memory_p95_pct: float | None = Field(default=None, ge=0, le=100)
    network_gb: float | None = Field(default=None, ge=0)
    disk_used_pct: float | None = Field(default=None, ge=0, le=100)
    source: DataSource

    @model_validator(mode="after")
    def require_at_least_one_metric(self) -> TelemetryDaily:
        metrics = (
            self.cpu_mean_pct,
            self.cpu_p95_pct,
            self.memory_mean_pct,
            self.memory_p95_pct,
            self.network_gb,
            self.disk_used_pct,
        )
        if all(value is None for value in metrics):
            raise ValueError("telemetry row must contain at least one metric")
        return self


class Dependency(DomainModel):
    source_resource_id: str = Field(min_length=1)
    target_resource_id: str = Field(min_length=1)
    relationship: Literal["routes_to", "reads_writes", "attached_to", "stores_in"]

    @model_validator(mode="after")
    def disallow_self_reference(self) -> Dependency:
        if self.source_resource_id == self.target_resource_id:
            raise ValueError("dependency cannot point to itself")
        return self


class PriceCard(DomainModel):
    sku_key: str = Field(min_length=1)
    service_type: str = Field(min_length=1)
    region: str = Field(min_length=1)
    unit: Literal["instance_hour", "gb_month"]
    unit_price_usd: float = Field(ge=0)
    effective_date: date
    source_url: HttpUrl
    source_type: Literal["CONTROLLED_DEMO_RATE", "GCP_CATALOG"]


class CarbonFactor(DomainModel):
    region: str = Field(min_length=1)
    gco2e_per_kwh: float = Field(gt=0)
    pue: float = Field(ge=1, le=3)
    effective_date: date
    source_url: HttpUrl
    source_type: Literal["CONTROLLED_DEMO_FACTOR", "VERIFIED_FACTOR"]


class SimulationRun(DomainModel):
    simulation_id: str = Field(min_length=1)
    resource_id: str = Field(min_length=1)
    request_json: dict[str, Any]
    result_json: dict[str, Any]
    method_version: str = Field(min_length=1)
    data_version: str = Field(min_length=1)
    created_at: datetime


class ResourceCatalog(DomainModel):
    resources: list[Resource]
    telemetry: list[TelemetryDaily]
    dependencies: list[Dependency]
    price_cards: list[PriceCard]
    carbon_factors: list[CarbonFactor]
    data_version: str

    @model_validator(mode="after")
    def validate_references(self) -> ResourceCatalog:
        resource_ids = {resource.resource_id for resource in self.resources}
        if len(resource_ids) != len(self.resources):
            raise ValueError("resource_id values must be unique")

        telemetry_orphans = {
            row.resource_id for row in self.telemetry if row.resource_id not in resource_ids
        }
        if telemetry_orphans:
            raise ValueError(f"telemetry references missing resources: {telemetry_orphans}")

        edge_orphans = {
            endpoint
            for edge in self.dependencies
            for endpoint in (edge.source_resource_id, edge.target_resource_id)
            if endpoint not in resource_ids
        }
        if edge_orphans:
            raise ValueError(f"dependencies reference missing resources: {edge_orphans}")
        return self


class DataStatus(DomainModel):
    requested_mode: Literal["auto", "local", "bigquery"]
    active_mode: Literal["local", "bigquery"]
    display_source: DataSource
    data_version: str
    resource_count: int = Field(ge=0)
    fallback_reason: str | None = None
