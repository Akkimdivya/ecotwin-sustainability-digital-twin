"""Immutable API models for a versioned EcoTwin topology snapshot."""

from __future__ import annotations

from datetime import datetime
from typing import Any, Literal

from pydantic import ConfigDict, Field

from .domain import DataSource, DomainModel, ResourceType

TwinNodeState = Literal[
    "healthy",
    "idle",
    "over_provisioned",
    "storage_waste",
    "unassessed",
]


class FrozenTwinModel(DomainModel):
    """Prevent accidental replacement of snapshot fields after construction."""

    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True, frozen=True)


class TwinMetricSummary(FrozenTwinModel):
    sample_days: int = Field(ge=0)
    window_start: str | None = None
    window_end: str | None = None
    cpu_mean_pct: float | None = Field(default=None, ge=0, le=100)
    cpu_p95_pct: float | None = Field(default=None, ge=0, le=100)
    memory_p95_pct: float | None = Field(default=None, ge=0, le=100)
    network_gb_mean: float | None = Field(default=None, ge=0)
    disk_used_pct: float | None = Field(default=None, ge=0, le=100)


class TwinNode(FrozenTwinModel):
    id: str
    name: str
    type: ResourceType
    state: TwinNodeState
    state_reason: str
    project_id: str
    region: str
    zone: str | None = None
    provider_status: str
    configuration: dict[str, Any]
    labels: dict[str, str]
    metrics: TwinMetricSummary
    incoming_count: int = Field(ge=0)
    outgoing_count: int = Field(ge=0)
    source: DataSource
    observed_at: datetime


class TwinEdge(FrozenTwinModel):
    id: str
    source: str
    target: str
    relationship: Literal["routes_to", "reads_writes", "attached_to", "stores_in"]


class TwinSummary(FrozenTwinModel):
    total_nodes: int = Field(ge=0)
    total_edges: int = Field(ge=0)
    healthy: int = Field(ge=0)
    idle: int = Field(ge=0)
    over_provisioned: int = Field(ge=0)
    storage_waste: int = Field(ge=0)
    unassessed: int = Field(ge=0)


class TwinSnapshot(FrozenTwinModel):
    snapshot_id: str
    snapshot_at: datetime
    data_version: str
    data_mode: DataSource
    active_repository: Literal["local", "bigquery"]
    nodes: tuple[TwinNode, ...]
    edges: tuple[TwinEdge, ...]
    summary: TwinSummary


class TwinNodeDetail(FrozenTwinModel):
    snapshot_id: str
    node: TwinNode
    incoming_edges: tuple[TwinEdge, ...]
    outgoing_edges: tuple[TwinEdge, ...]
