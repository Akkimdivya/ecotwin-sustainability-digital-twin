"""Select BigQuery or the validated local fallback."""

from __future__ import annotations

import logging
from dataclasses import dataclass

from app.config import Settings
from app.models import ResourceCatalog

from .base import CatalogRepository
from .bigquery import BigQueryRepository
from .local import LocalJsonRepository

LOGGER = logging.getLogger(__name__)


@dataclass(frozen=True, slots=True)
class RepositorySelection:
    repository: CatalogRepository
    catalog: ResourceCatalog
    active_mode: str
    fallback_reason: str | None = None


def select_repository(settings: Settings) -> RepositorySelection:
    local = LocalJsonRepository(settings.data_dir)

    if settings.data_mode == "local":
        catalog = local.load_catalog()
        return RepositorySelection(local, catalog, "local")

    if not settings.gcp_project:
        if settings.data_mode == "bigquery":
            raise ValueError("ECOTWIN_GCP_PROJECT is required in bigquery mode")
        catalog = local.load_catalog()
        return RepositorySelection(
            local,
            catalog,
            "local",
            "No Google Cloud project configured; using validated local demo data.",
        )

    try:
        remote = BigQueryRepository(
            project=settings.gcp_project,
            dataset=settings.bigquery_dataset,
            location=settings.bigquery_location,
        )
        remote.healthcheck()
        catalog = remote.load_catalog()
        return RepositorySelection(remote, catalog, "bigquery")
    except Exception as exc:
        if settings.data_mode == "bigquery":
            raise
        LOGGER.warning("BigQuery unavailable; activating local fallback: %s", type(exc).__name__)
        catalog = local.load_catalog()
        return RepositorySelection(
            local,
            catalog,
            "local",
            f"BigQuery unavailable ({type(exc).__name__}); using validated local demo data.",
        )
