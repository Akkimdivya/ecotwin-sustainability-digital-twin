"""Durable simulation retrieval for Cloud Run instances."""

from __future__ import annotations

import json
from datetime import UTC, datetime
from typing import Any, Protocol

from app.models import RightsizeRequest, RightsizeResult


class SimulationStore(Protocol):
    """Store a deterministic result so requests can move between instances."""

    def save(self, request: RightsizeRequest, result: RightsizeResult) -> None: ...

    def get(self, simulation_id: str) -> RightsizeResult | None: ...


class MemorySimulationStore:
    """Local-development fallback; Cloud Run uses BigQuerySimulationStore."""

    def __init__(self) -> None:
        self._items: dict[str, RightsizeResult] = {}

    def save(self, request: RightsizeRequest, result: RightsizeResult) -> None:
        self._items[result.simulation_id] = result

    def get(self, simulation_id: str) -> RightsizeResult | None:
        return self._items.get(simulation_id)


class BigQuerySimulationStore:
    """Persist controlled simulation evidence in the existing BigQuery audit table."""

    def __init__(
        self,
        project: str,
        dataset: str,
        location: str,
        client: Any | None = None,
    ) -> None:
        from google.cloud import bigquery

        self.project = project
        self.dataset = dataset
        self.location = location
        self._bigquery = bigquery
        self.client = client or bigquery.Client(project=project, location=location)

    @property
    def table_id(self) -> str:
        return f"`{self.project}.{self.dataset}.simulation_runs`"

    def save(self, request: RightsizeRequest, result: RightsizeResult) -> None:
        query = f"""
            MERGE {self.table_id} AS target
            USING (SELECT @simulation_id AS simulation_id) AS source
            ON target.simulation_id = source.simulation_id
            WHEN NOT MATCHED THEN
              INSERT (
                simulation_id, resource_id, request_json, result_json,
                method_version, data_version, created_at
              )
              VALUES (
                source.simulation_id, @resource_id, PARSE_JSON(@request_json),
                PARSE_JSON(@result_json), @method_version, @data_version,
                TIMESTAMP(@created_at)
              )
        """
        parameters = [
            self._bigquery.ScalarQueryParameter("simulation_id", "STRING", result.simulation_id),
            self._bigquery.ScalarQueryParameter("resource_id", "STRING", result.resource_id),
            self._bigquery.ScalarQueryParameter(
                "request_json",
                "STRING",
                json.dumps(request.model_dump(mode="json"), sort_keys=True),
            ),
            self._bigquery.ScalarQueryParameter(
                "result_json", "STRING", json.dumps(result.model_dump(mode="json"), sort_keys=True)
            ),
            self._bigquery.ScalarQueryParameter("method_version", "STRING", result.method_version),
            self._bigquery.ScalarQueryParameter("data_version", "STRING", result.data_version),
            self._bigquery.ScalarQueryParameter(
                "created_at", "TIMESTAMP", datetime.now(UTC)
            ),
        ]
        self.client.query(
            query,
            job_config=self._bigquery.QueryJobConfig(query_parameters=parameters),
        ).result()

    def get(self, simulation_id: str) -> RightsizeResult | None:
        query = f"""
            SELECT result_json
            FROM {self.table_id}
            WHERE simulation_id = @simulation_id
            ORDER BY created_at DESC
            LIMIT 1
        """
        rows = list(
            self.client.query(
                query,
                job_config=self._bigquery.QueryJobConfig(
                    query_parameters=[
                        self._bigquery.ScalarQueryParameter(
                            "simulation_id", "STRING", simulation_id
                        )
                    ]
                ),
            ).result()
        )
        if not rows:
            return None
        payload = dict(rows[0].items())["result_json"]
        if isinstance(payload, str):
            payload = json.loads(payload)
        return RightsizeResult.model_validate(payload)
