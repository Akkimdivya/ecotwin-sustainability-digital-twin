"""Repository interface used by API and later simulation modules."""

from __future__ import annotations

from typing import Protocol

from app.models import ResourceCatalog


class CatalogRepository(Protocol):
    mode: str

    def load_catalog(self) -> ResourceCatalog: ...

    def healthcheck(self) -> None: ...
