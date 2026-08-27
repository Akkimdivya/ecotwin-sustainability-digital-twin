from __future__ import annotations

from pathlib import Path

from app.config import Settings
from app.main import create_app
from fastapi.testclient import TestClient

DATA_DIR = Path(__file__).resolve().parents[2] / "data"


def test_health_and_controlled_data_endpoints() -> None:
    settings = Settings(
        app_env="test",
        data_mode="local",
        data_dir=DATA_DIR,
        gcp_project=None,
        bigquery_dataset="ecotwin_demo",
        bigquery_location="us-central1",
        log_level="WARNING",
    )

    with TestClient(create_app(settings)) as client:
        health = client.get("/api/health")
        status = client.get("/api/data-status")
        resources = client.get("/api/resources")
        vm_telemetry = client.get("/api/telemetry", params={"resource_id": "vm-api-01"})
        twin = client.get("/api/twin")
        node = client.get("/api/twin/nodes/vm-api-01")
        missing_node = client.get("/api/twin/nodes/does-not-exist")
        dashboard = client.get("/")

    assert health.status_code == 200
    assert health.json()["status"] == "ok"
    assert status.json()["display_source"] == "CONTROLLED_DEMO"
    assert status.json()["resource_count"] == 9
    assert len(resources.json()) == 9
    assert len(vm_telemetry.json()) == 7
    assert twin.status_code == 200
    assert twin.json()["summary"]["total_nodes"] == 9
    assert twin.json()["summary"]["total_edges"] == 7
    assert node.json()["node"]["state"] == "over_provisioned"
    assert len(node.json()["incoming_edges"]) == 3
    assert missing_node.status_code == 404
    assert dashboard.status_code == 200
    assert "EcoTwin" in dashboard.text


def test_auto_mode_exposes_local_fallback() -> None:
    settings = Settings(
        app_env="test",
        data_mode="auto",
        data_dir=DATA_DIR,
        gcp_project=None,
        bigquery_dataset="ecotwin_demo",
        bigquery_location="us-central1",
        log_level="WARNING",
    )

    with TestClient(create_app(settings)) as client:
        payload = client.get("/api/data-status").json()

    assert payload["active_mode"] == "local"
    assert payload["display_source"] == "LOCAL_DEMO_FALLBACK"
    assert "No Google Cloud project" in payload["fallback_reason"]
