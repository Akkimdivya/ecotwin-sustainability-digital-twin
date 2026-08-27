from __future__ import annotations

from pathlib import Path

import pytest
from app.models import Dependency, ResourceCatalog
from app.repositories.local import LocalJsonRepository
from pydantic import ValidationError

DATA_DIR = Path(__file__).resolve().parents[2] / "data"


def test_controlled_catalog_is_valid_and_connected() -> None:
    catalog = LocalJsonRepository(DATA_DIR).load_catalog()

    assert catalog.data_version == "demo-2026-08-27-v1"
    assert len(catalog.resources) == 9
    assert len(catalog.telemetry) >= 28
    assert len(catalog.dependencies) == 7
    assert {resource.source for resource in catalog.resources} == {"CONTROLLED_DEMO"}


def test_catalog_rejects_orphan_dependency() -> None:
    catalog = LocalJsonRepository(DATA_DIR).load_catalog()
    payload = catalog.model_dump()
    payload["dependencies"].append(
        Dependency(
            source_resource_id="missing-resource",
            target_resource_id="vm-api-01",
            relationship="routes_to",
        ).model_dump()
    )

    with pytest.raises(ValidationError, match="dependencies reference missing resources"):
        ResourceCatalog.model_validate(payload)


def test_demo_contains_each_required_waste_scenario() -> None:
    catalog = LocalJsonRepository(DATA_DIR).load_catalog()
    resources = {resource.resource_id: resource for resource in catalog.resources}

    assert resources["vm-api-01"].vcpu == 4
    assert resources["vm-batch-02"].status == "RUNNING"
    assert resources["disk-orphan-01"].attached_to is None
    assert resources["disk-orphan-01"].unattached_since is not None
