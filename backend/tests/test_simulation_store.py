from __future__ import annotations

import json
from pathlib import Path

from app.models import RightsizeRequest
from app.repositories.local import LocalJsonRepository
from app.repositories.simulation_store import BigQuerySimulationStore
from app.services import build_twin_snapshot, simulate_rightsize

DATA_DIR = Path(__file__).resolve().parents[2] / "data"


class FakeQueryJob:
    def __init__(self, rows: list[FakeRow]) -> None:
        self.rows = rows

    def result(self) -> list[FakeRow]:
        return self.rows


class FakeRow:
    def __init__(self, payload: dict[str, object]) -> None:
        self.payload = payload

    def items(self):
        return self.payload.items()


class FakeBigQueryClient:
    def __init__(self) -> None:
        self.queries: list[str] = []
        self.result_json: dict[str, object] | None = None

    def query(self, query: str, *, job_config):
        self.queries.append(query)
        if "MERGE" in query:
            parameters = {
                parameter.name: parameter.value for parameter in job_config.query_parameters
            }
            self.result_json = json.loads(parameters["result_json"])
            return FakeQueryJob([])
        rows = [FakeRow({"result_json": self.result_json})] if self.result_json else []
        return FakeQueryJob(rows)


def test_bigquery_store_persists_and_retrieves_a_deterministic_result() -> None:
    catalog = LocalJsonRepository(DATA_DIR).load_catalog()
    snapshot = build_twin_snapshot(
        catalog,
        data_mode="CONTROLLED_DEMO",
        active_repository="local",
    )
    request = RightsizeRequest(
        resource_id="vm-api-01",
        proposed_vcpu=2,
        proposed_memory_gb=8,
    )
    result = simulate_rightsize(catalog, snapshot, request)
    client = FakeBigQueryClient()
    store = BigQuerySimulationStore(
        "test-project",
        "ecotwin_demo",
        "us-central1",
        client=client,
    )

    store.save(request, result)

    assert store.get(result.simulation_id) == result
    assert "MERGE" in client.queries[0]
    assert "@simulation_id" in client.queries[1]
