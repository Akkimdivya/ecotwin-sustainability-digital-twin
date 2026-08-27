"""Create EcoTwin BigQuery tables and load the validated controlled dataset."""

from __future__ import annotations

import argparse
from pathlib import Path
from typing import Any

from app.repositories.local import LocalJsonRepository
from google.cloud import bigquery

SCHEMAS: dict[str, list[bigquery.SchemaField]] = {
    "metadata": [
        bigquery.SchemaField("data_version", "STRING", mode="REQUIRED"),
        bigquery.SchemaField("source", "STRING", mode="REQUIRED"),
        bigquery.SchemaField("description", "STRING", mode="REQUIRED"),
        bigquery.SchemaField("observed_at", "TIMESTAMP", mode="REQUIRED"),
    ],
    "resources": [
        bigquery.SchemaField("resource_id", "STRING", mode="REQUIRED"),
        bigquery.SchemaField("name", "STRING", mode="REQUIRED"),
        bigquery.SchemaField("project_id", "STRING", mode="REQUIRED"),
        bigquery.SchemaField("service_type", "STRING", mode="REQUIRED"),
        bigquery.SchemaField("region", "STRING", mode="REQUIRED"),
        bigquery.SchemaField("zone", "STRING"),
        bigquery.SchemaField("machine_type", "STRING"),
        bigquery.SchemaField("vcpu", "INTEGER"),
        bigquery.SchemaField("memory_gb", "FLOAT"),
        bigquery.SchemaField("storage_gb", "FLOAT"),
        bigquery.SchemaField("storage_type", "STRING"),
        bigquery.SchemaField("status", "STRING", mode="REQUIRED"),
        bigquery.SchemaField("attached_to", "STRING"),
        bigquery.SchemaField("unattached_since", "DATE"),
        bigquery.SchemaField("labels", "JSON"),
        bigquery.SchemaField("source", "STRING", mode="REQUIRED"),
        bigquery.SchemaField("observed_at", "TIMESTAMP", mode="REQUIRED"),
    ],
    "telemetry_daily": [
        bigquery.SchemaField("resource_id", "STRING", mode="REQUIRED"),
        bigquery.SchemaField("date", "DATE", mode="REQUIRED"),
        bigquery.SchemaField("cpu_mean_pct", "FLOAT"),
        bigquery.SchemaField("cpu_p95_pct", "FLOAT"),
        bigquery.SchemaField("memory_mean_pct", "FLOAT"),
        bigquery.SchemaField("memory_p95_pct", "FLOAT"),
        bigquery.SchemaField("network_gb", "FLOAT"),
        bigquery.SchemaField("disk_used_pct", "FLOAT"),
        bigquery.SchemaField("source", "STRING", mode="REQUIRED"),
    ],
    "dependencies": [
        bigquery.SchemaField("source_resource_id", "STRING", mode="REQUIRED"),
        bigquery.SchemaField("target_resource_id", "STRING", mode="REQUIRED"),
        bigquery.SchemaField("relationship", "STRING", mode="REQUIRED"),
    ],
    "price_cards": [
        bigquery.SchemaField("sku_key", "STRING", mode="REQUIRED"),
        bigquery.SchemaField("service_type", "STRING", mode="REQUIRED"),
        bigquery.SchemaField("region", "STRING", mode="REQUIRED"),
        bigquery.SchemaField("unit", "STRING", mode="REQUIRED"),
        bigquery.SchemaField("unit_price_usd", "NUMERIC", mode="REQUIRED"),
        bigquery.SchemaField("effective_date", "DATE", mode="REQUIRED"),
        bigquery.SchemaField("source_url", "STRING", mode="REQUIRED"),
        bigquery.SchemaField("source_type", "STRING", mode="REQUIRED"),
    ],
    "carbon_factors": [
        bigquery.SchemaField("region", "STRING", mode="REQUIRED"),
        bigquery.SchemaField("gco2e_per_kwh", "FLOAT", mode="REQUIRED"),
        bigquery.SchemaField("pue", "FLOAT", mode="REQUIRED"),
        bigquery.SchemaField("effective_date", "DATE", mode="REQUIRED"),
        bigquery.SchemaField("source_url", "STRING", mode="REQUIRED"),
        bigquery.SchemaField("source_type", "STRING", mode="REQUIRED"),
    ],
    "simulation_runs": [
        bigquery.SchemaField("simulation_id", "STRING", mode="REQUIRED"),
        bigquery.SchemaField("resource_id", "STRING", mode="REQUIRED"),
        bigquery.SchemaField("request_json", "JSON", mode="REQUIRED"),
        bigquery.SchemaField("result_json", "JSON", mode="REQUIRED"),
        bigquery.SchemaField("method_version", "STRING", mode="REQUIRED"),
        bigquery.SchemaField("data_version", "STRING", mode="REQUIRED"),
        bigquery.SchemaField("created_at", "TIMESTAMP", mode="REQUIRED"),
    ],
}


def model_rows(models: list[Any]) -> list[dict[str, Any]]:
    return [model.model_dump(mode="json") for model in models]


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--project", required=True, help="Google Cloud project ID")
    parser.add_argument("--dataset", default="ecotwin_demo")
    parser.add_argument("--location", default="us-central1")
    parser.add_argument(
        "--data-dir",
        type=Path,
        default=Path(__file__).resolve().parents[2] / "data",
    )
    parser.add_argument(
        "--apply",
        action="store_true",
        help=(
            "Create/replace cloud tables. Without this flag the script only "
            "validates and previews."
        ),
    )
    args = parser.parse_args()

    repository = LocalJsonRepository(args.data_dir.resolve())
    catalog = repository.load_catalog()
    table_rows: dict[str, list[dict[str, Any]]] = {
        "metadata": [
            {
                "data_version": catalog.data_version,
                "source": "CONTROLLED_DEMO",
                "description": "Validated synthetic EcoTwin Checkpoint 2 dataset.",
                "observed_at": "2026-08-27T00:00:00Z",
            }
        ],
        "resources": model_rows(catalog.resources),
        "telemetry_daily": model_rows(catalog.telemetry),
        "dependencies": model_rows(catalog.dependencies),
        "price_cards": model_rows(catalog.price_cards),
        "carbon_factors": model_rows(catalog.carbon_factors),
    }

    print(f"Validated {catalog.data_version} for {args.project}.{args.dataset}")
    for name, rows in table_rows.items():
        print(f"  {name}: {len(rows)} rows")
    if not args.apply:
        print("Preview only. Add --apply to create/replace BigQuery tables.")
        return

    client = bigquery.Client(project=args.project, location=args.location)
    dataset_id = f"{args.project}.{args.dataset}"
    dataset = bigquery.Dataset(dataset_id)
    dataset.location = args.location
    dataset.description = "Controlled, synthetic EcoTwin Checkpoint 2 data"
    client.create_dataset(dataset, exists_ok=True)

    for table_name, rows in table_rows.items():
        table_id = f"{dataset_id}.{table_name}"
        table = bigquery.Table(table_id, schema=SCHEMAS[table_name])
        if table_name == "telemetry_daily":
            table.time_partitioning = bigquery.TimePartitioning(field="date")
            table.clustering_fields = ["resource_id"]
        elif table_name == "resources":
            table.clustering_fields = ["service_type", "region"]
        elif table_name == "price_cards":
            table.clustering_fields = ["service_type", "region"]
        client.create_table(table, exists_ok=True)
        job_config = bigquery.LoadJobConfig(
            schema=SCHEMAS[table_name],
            write_disposition=bigquery.WriteDisposition.WRITE_TRUNCATE,
        )
        job = client.load_table_from_json(rows, table_id, job_config=job_config)
        job.result()
        print(f"Loaded {len(rows)} rows into {table_id}")

    simulation_table_id = f"{dataset_id}.simulation_runs"
    simulation_table = bigquery.Table(
        simulation_table_id,
        schema=SCHEMAS["simulation_runs"],
    )
    simulation_table.time_partitioning = bigquery.TimePartitioning(field="created_at")
    simulation_table.clustering_fields = ["resource_id", "method_version"]
    client.create_table(simulation_table, exists_ok=True)
    print(f"Ensured empty simulation history table: {simulation_table_id}")


if __name__ == "__main__":
    main()
