-- EcoTwin Checkpoint 2 controlled-data schema.
-- Run in a project selected by gcloud/bq. Change the location if the app region differs.

CREATE SCHEMA IF NOT EXISTS `ecotwin_demo`
OPTIONS (
  location = "us-central1",
  description = "Controlled, synthetic EcoTwin Checkpoint 2 data"
);

CREATE TABLE IF NOT EXISTS `ecotwin_demo.metadata` (
  data_version STRING NOT NULL,
  source STRING NOT NULL,
  description STRING NOT NULL,
  observed_at TIMESTAMP NOT NULL
);

CREATE TABLE IF NOT EXISTS `ecotwin_demo.resources` (
  resource_id STRING NOT NULL,
  name STRING NOT NULL,
  project_id STRING NOT NULL,
  service_type STRING NOT NULL,
  region STRING NOT NULL,
  zone STRING,
  machine_type STRING,
  vcpu INT64,
  memory_gb FLOAT64,
  storage_gb FLOAT64,
  storage_type STRING,
  status STRING NOT NULL,
  attached_to STRING,
  unattached_since DATE,
  labels JSON,
  source STRING NOT NULL,
  observed_at TIMESTAMP NOT NULL
)
CLUSTER BY service_type, region;

CREATE TABLE IF NOT EXISTS `ecotwin_demo.telemetry_daily` (
  resource_id STRING NOT NULL,
  date DATE NOT NULL,
  cpu_mean_pct FLOAT64,
  cpu_p95_pct FLOAT64,
  memory_mean_pct FLOAT64,
  memory_p95_pct FLOAT64,
  network_gb FLOAT64,
  disk_used_pct FLOAT64,
  source STRING NOT NULL
)
PARTITION BY date
CLUSTER BY resource_id;

CREATE TABLE IF NOT EXISTS `ecotwin_demo.dependencies` (
  source_resource_id STRING NOT NULL,
  target_resource_id STRING NOT NULL,
  relationship STRING NOT NULL
);

CREATE TABLE IF NOT EXISTS `ecotwin_demo.price_cards` (
  sku_key STRING NOT NULL,
  service_type STRING NOT NULL,
  region STRING NOT NULL,
  unit STRING NOT NULL,
  unit_price_usd NUMERIC NOT NULL,
  effective_date DATE NOT NULL,
  source_url STRING NOT NULL,
  source_type STRING NOT NULL
)
CLUSTER BY service_type, region;

CREATE TABLE IF NOT EXISTS `ecotwin_demo.carbon_factors` (
  region STRING NOT NULL,
  gco2e_per_kwh FLOAT64 NOT NULL,
  pue FLOAT64 NOT NULL,
  effective_date DATE NOT NULL,
  source_url STRING NOT NULL,
  source_type STRING NOT NULL
);

CREATE TABLE IF NOT EXISTS `ecotwin_demo.simulation_runs` (
  simulation_id STRING NOT NULL,
  resource_id STRING NOT NULL,
  request_json JSON NOT NULL,
  result_json JSON NOT NULL,
  method_version STRING NOT NULL,
  data_version STRING NOT NULL,
  created_at TIMESTAMP NOT NULL
)
PARTITION BY DATE(created_at)
CLUSTER BY resource_id, method_version;

