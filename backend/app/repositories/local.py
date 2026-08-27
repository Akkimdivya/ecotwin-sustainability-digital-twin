"""Validated local JSON repository used for development and demo fallback."""

from __future__ import annotations

import json
from pathlib import Path
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


class LocalJsonRepository:
    mode = "local"

    def __init__(self, data_dir: Path) -> None:
        self.data_dir = data_dir

    def _read_json(self, filename: str) -> Any:
        path = self.data_dir / filename
        if not path.is_file():
            raise FileNotFoundError(f"required data file not found: {path}")
        with path.open("r", encoding="utf-8") as handle:
            return json.load(handle)

    def _read_list(self, filename: str, model: type[T]) -> list[T]:
        return TypeAdapter(list[model]).validate_python(self._read_json(filename))

    def load_catalog(self) -> ResourceCatalog:
        metadata = self._read_json("metadata.json")
        return ResourceCatalog(
            resources=self._read_list("resources.json", Resource),
            telemetry=self._read_list("telemetry.json", TelemetryDaily),
            dependencies=self._read_list("dependencies.json", Dependency),
            price_cards=self._read_list("pricing.json", PriceCard),
            carbon_factors=self._read_list("carbon_factors.json", CarbonFactor),
            data_version=metadata["data_version"],
        )

    def healthcheck(self) -> None:
        self.load_catalog()
