from __future__ import annotations

from pathlib import Path

from app.repositories.local import LocalJsonRepository
from app.services import build_twin_snapshot

DATA_DIR = Path(__file__).resolve().parents[2] / "data"


def test_twin_builder_creates_deterministic_valid_topology() -> None:
    catalog = LocalJsonRepository(DATA_DIR).load_catalog()

    first = build_twin_snapshot(
        catalog,
        data_mode="CONTROLLED_DEMO",
        active_repository="local",
    )
    second = build_twin_snapshot(
        catalog,
        data_mode="CONTROLLED_DEMO",
        active_repository="local",
    )

    assert first.snapshot_id == second.snapshot_id
    assert first.summary.total_nodes == 9
    assert first.summary.total_edges == 7
    assert len({node.id for node in first.nodes}) == 9
    assert all(edge.source in {node.id for node in first.nodes} for edge in first.edges)
    assert all(edge.target in {node.id for node in first.nodes} for edge in first.edges)


def test_twin_builder_assigns_evidence_backed_states() -> None:
    catalog = LocalJsonRepository(DATA_DIR).load_catalog()
    snapshot = build_twin_snapshot(
        catalog,
        data_mode="CONTROLLED_DEMO",
        active_repository="local",
    )
    states = {node.id: node.state for node in snapshot.nodes}

    assert states["vm-api-01"] == "over_provisioned"
    assert states["vm-batch-02"] == "idle"
    assert states["disk-orphan-01"] == "storage_waste"
    assert states["vm-web-01"] == "healthy"
    assert snapshot.summary.over_provisioned == 1
    assert snapshot.summary.idle == 1
    assert snapshot.summary.storage_waste == 1
