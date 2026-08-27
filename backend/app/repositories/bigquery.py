"""BigQuery repository for the controlled EcoTwin dataset."""

from __future__ import annotations

import re
from collections.abc import Iterable
from typing import Any, TypeVar

from pydantic import BaseModel, TypeAdapter

from app.models import (
    CarbonFactor,
    Dependency,
    PriceCard,
    Resource,
    ResourceCatalog,
    TelemetryDaily,
)

T = TypeVar("T", bound=BaseModel)
_IDENTIFIER = re.compile(r"^[A-Za-z0-9_-]+$")


class BigQueryRepository:
    mode = "bigquery"

    def __init__(self, project: str, dataset: str, location: str) -> None:
        if not _IDENTIFIER.fullmatch(project) or not _IDENTIFIER.fullmatch(dataset):
            raise ValueError("project and dataset must contain only letters, numbers, _, or -")
        from google.cloud import bigquery

        self.project = project
        self.dataset = dataset
        self.location = location
        self.client = bigquery.Client(project=project, location=location)

    def _rows(self, table: str) -> Iterable[dict[str, Any]]:
        query = f"SELECT * FROM `{self.project}.{self.dataset}.{table}`"  # noqa: S608
        for row in self.client.query(query).result():
            yield dict(row.items())

    def _typed_rows(self, table: str, model: type[T]) -> list[T]:
        return TypeAdapter(list[model]).validate_python(list(self._rows(table)))

    def load_catalog(self) -> ResourceCatalog:
        metadata_rows = list(self._rows("metadata"))
        if len(metadata_rows) != 1:
            raise ValueError("metadata table must contain exactly one row")
        return ResourceCatalog(
            resources=self._typed_rows("resources", Resource),
            telemetry=self._typed_rows("telemetry_daily", TelemetryDaily),
            dependencies=self._typed_rows("dependencies", Dependency),
            price_cards=self._typed_rows("price_cards", PriceCard),
            carbon_factors=self._typed_rows("carbon_factors", CarbonFactor),
            data_version=metadata_rows[0]["data_version"],
        )

    def healthcheck(self) -> None:
        table = f"{self.project}.{self.dataset}.metadata"
        self.client.get_table(table)
