"""Environment-backed settings for EcoTwin."""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path
from typing import Literal

DataMode = Literal["auto", "local", "bigquery"]


def _default_data_dir() -> Path:
    return Path(__file__).resolve().parents[2] / "data"


@dataclass(frozen=True, slots=True)
class Settings:
    app_env: str
    data_mode: DataMode
    data_dir: Path
    gcp_project: str | None
    bigquery_dataset: str
    bigquery_location: str
    log_level: str

    @classmethod
    def from_env(cls) -> Settings:
        raw_mode = os.getenv("ECOTWIN_DATA_MODE", "auto").lower()
        if raw_mode not in {"auto", "local", "bigquery"}:
            raise ValueError("ECOTWIN_DATA_MODE must be auto, local, or bigquery")

        data_dir = Path(os.getenv("ECOTWIN_DATA_DIR", str(_default_data_dir()))).resolve()
        project = os.getenv("ECOTWIN_GCP_PROJECT") or os.getenv("GOOGLE_CLOUD_PROJECT")
        return cls(
            app_env=os.getenv("ECOTWIN_APP_ENV", "development"),
            data_mode=raw_mode,  # type: ignore[arg-type]
            data_dir=data_dir,
            gcp_project=project,
            bigquery_dataset=os.getenv("ECOTWIN_BIGQUERY_DATASET", "ecotwin_demo"),
            bigquery_location=os.getenv("ECOTWIN_BIGQUERY_LOCATION", "us-central1"),
            log_level=os.getenv("ECOTWIN_LOG_LEVEL", "INFO").upper(),
        )
