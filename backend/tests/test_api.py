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
        findings = client.get("/api/findings")
        opportunities = client.get("/api/opportunities")
        summary = client.get("/api/summary")
        methodology = client.get("/api/methodology")
        finding = client.get("/api/findings/over-provisioned-compute::vm-api-01")
        missing_finding = client.get("/api/findings/does-not-exist")
        simulation = client.post(
            "/api/simulations",
            json={
                "resource_id": "vm-api-01",
                "proposed_vcpu": 2,
                "proposed_memory_gb": 8,
                "growth_buffer_pct": 20,
            },
        )
        invalid_simulation = client.post(
            "/api/simulations",
            json={
                "resource_id": "vm-api-01",
                "proposed_vcpu": 4,
                "proposed_memory_gb": 16,
            },
        )
        stored_simulation = client.get("/api/simulations/sim-6db42a0b799b9c24")
        missing_simulation = client.get("/api/simulations/does-not-exist")
        explanation_by_id = client.post("/api/simulations/sim-6db42a0b799b9c24/explain")
        ai_status = client.get("/api/ai-status")
        explanation = client.post(
            "/api/explanations",
            json={
                "resource_id": "vm-api-01",
                "proposed_vcpu": 2,
                "proposed_memory_gb": 8,
                "growth_buffer_pct": 20,
            },
        )
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
    assert findings.status_code == 200
    assert opportunities.status_code == 200
    assert findings.json()["summary"]["total_findings"] == 3
    assert summary.status_code == 200
    assert summary.json()["resource_count"] == 9
    assert summary.json()["opportunity_count"] == 3
    assert methodology.status_code == 200
    assert methodology.json()["simulation_method_version"] == "simulation-v1.0"
    assert finding.status_code == 200
    assert finding.json()["resource_id"] == "vm-api-01"
    assert missing_finding.status_code == 404
    assert simulation.status_code == 200
    assert simulation.json()["impact"]["monthly_cost_savings_usd"] == 48.91
    assert simulation.json()["risk"]["level"] == "HIGH"
    assert invalid_simulation.status_code == 422
    assert stored_simulation.status_code == 200
    assert stored_simulation.json() == simulation.json()
    assert missing_simulation.status_code == 404
    assert explanation_by_id.status_code == 200
    assert explanation_by_id.json()["simulation_id"] == simulation.json()["simulation_id"]
    assert ai_status.json()["mode"] == "FALLBACK_READY"
    assert ai_status.json()["api_key_required"] is False
    assert explanation.status_code == 200
    assert explanation.json()["provider"] == "DETERMINISTIC_FALLBACK"
    assert explanation.json()["simulation_id"] == simulation.json()["simulation_id"]
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
