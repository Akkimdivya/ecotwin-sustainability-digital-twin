"""Validate all controlled JSON files and their cross-file references."""

from __future__ import annotations

import argparse
from pathlib import Path

from app.repositories.local import LocalJsonRepository


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--data-dir",
        type=Path,
        default=Path(__file__).resolve().parents[2] / "data",
    )
    args = parser.parse_args()

    catalog = LocalJsonRepository(args.data_dir.resolve()).load_catalog()
    print(f"Validated data version: {catalog.data_version}")
    print(f"Resources: {len(catalog.resources)}")
    print(f"Telemetry rows: {len(catalog.telemetry)}")
    print(f"Dependencies: {len(catalog.dependencies)}")
    print(f"Price cards: {len(catalog.price_cards)}")
    print(f"Carbon factors: {len(catalog.carbon_factors)}")


if __name__ == "__main__":
    main()
