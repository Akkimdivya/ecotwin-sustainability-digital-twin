# EcoTwin

**AI-powered sustainability digital twin and what-if simulator for cloud infrastructure.**

EcoTwin is a read-only decision-support prototype. It builds a virtual representation of cloud resources, identifies likely waste, and will simulate an optimization before any production change. Checkpoint 2 uses a clearly labeled, reproducible controlled dataset.

Repository: <https://github.com/Akkimdivya/ecotwin-sustainability-digital-twin>

Live application: <https://ecotwin-1075889318331.us-central1.run.app>

> Simulation only — no production changes.

## Current build status

Completed Modules 1 through 9. Module 10 submission assets are prepared:

- Module 1 - delivery foundation: repository, environment configuration, FastAPI service, health checks, Docker, CI and security exclusions.
- Module 2 - cloud data foundation: validated controlled dataset, live BigQuery schema and data, local fallback, read-only catalog APIs and tests.
- Module 3 - digital twin: immutable topology snapshots, validated dependency edges, evidence-backed node states and an interactive graph with node details.
- Module 4 - waste detection: explicit idle-compute, over-provisioning and unattached-storage rules with evidence, confidence, limitations and simulation eligibility.
- Module 5 - what-if simulation: deterministic before/after cost, estimated operational carbon, performance pressure, risk, confidence, assumptions and source cards.
- Module 6 - Gemini explanation: structured Vertex AI guidance grounded in the simulation JSON, schema validation, timeout, retry, per-simulation cache and deterministic demo-safe fallback.
- Module 7 - Frontend and visual design: polished control-plane UI, interactive dependency graph, evidence cards, session log and responsive layouts for desktop and mobile.
- Module 8 - Google Cloud deployment: public Cloud Run service, live BigQuery reads, Vertex AI through ADC, least-privilege runtime identity, structured request logging and scale-to-zero cost controls.
- Module 9 - Testing, validation and evidence: automated tests, linting, browser verification, deployment evidence and reproducible golden scenario notes.
- Module 10 - documentation and submission: README, architecture notes, submission copy, demo script, evidence index and checklist are prepared; official portal upload and video submission remain manual.

Google Cloud foundation verified on August 27, 2026:

- Project: `ecotwin-sustainability-2026`
- Region and BigQuery dataset location: `us-central1`
- Dataset: `ecotwin_demo`
- Data version: `demo-2026-08-27-v1`
- API read mode verified: `bigquery` with no fallback
- No API keys or service-account key files created

Next: upload the demo video and complete the remaining portal submission steps.

## Quick start

From the repository root in PowerShell:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r backend\requirements-dev.txt
$env:ECOTWIN_DATA_MODE = "local"
uvicorn app.main:app --app-dir backend --reload
```

Open:

- API documentation: <http://127.0.0.1:8000/docs>
- Health: <http://127.0.0.1:8000/api/health>
- Data status: <http://127.0.0.1:8000/api/data-status>

## Validate and test

```powershell
$env:PYTHONPATH = "backend"
python -m scripts.validate_data
pytest
ruff check backend
```

## Data APIs

| Endpoint | Purpose |
|---|---|
| `GET /api/health` | Service and repository health |
| `GET /api/data-status` | Active source, data version and fallback reason |
| `GET /api/summary` | Dashboard totals for cost, carbon and opportunities |
| `GET /api/resources` | Normalized resource inventory |
| `GET /api/telemetry?resource_id=...` | Daily controlled telemetry |
| `GET /api/dependencies` | Resource graph edges |
| `GET /api/price-cards` | Versioned controlled price assumptions |
| `GET /api/carbon-factors` | Versioned controlled carbon assumptions |
| `GET /api/twin` | Immutable digital-twin topology and summary |
| `GET /api/twin/nodes/{resource_id}` | Node configuration, telemetry and connections |
| `GET /api/findings` | Versioned waste report with thresholds and evidence |
| `GET /api/opportunities` | Alias for the same waste report, kept for module 6 parity |
| `GET /api/findings/{finding_id}` | One explainable optimization finding |
| `POST /api/simulations` | Run a read-only compute right-sizing scenario |
| `GET /api/simulations/{simulation_id}` | Retrieve a stored simulation result |
| `POST /api/simulations/{simulation_id}/explain` | Explain a stored simulation by ID |
| `GET /api/ai-status` | Gemini mode, model, location and credential policy |
| `POST /api/explanations` | Re-run the deterministic scenario and explain its exact result |
| `GET /api/methodology` | Versioned thresholds, assumptions and guardrails |

## Controlled data

`data/` contains nine synthetic GCP-shaped resources and seven days of telemetry for the core workloads. It intentionally includes:

- An over-provisioning candidate: `vm-api-01` with 4 vCPU.
- An idle candidate: `vm-batch-02`.
- A storage-waste candidate: `disk-orphan-01`, unattached for 21 days.
- Healthy resources to prevent every node being flagged.
- Seven dependency relationships for the future digital-twin graph.

Price cards and regional carbon factors are **controlled scenario assumptions**, not invoices or verified emissions. Their source type and effective date are stored with every value.

## BigQuery preview and load

The loader validates every row and every cross-resource reference before touching Google Cloud. It runs in preview mode unless `--apply` is supplied.

```powershell
Set-Location backend
python -m scripts.load_bigquery --project YOUR_PROJECT_ID
python -m scripts.load_bigquery --project YOUR_PROJECT_ID --apply
Set-Location ..
```

The apply command creates/replaces the controlled tables in `ecotwin_demo`. It does not create keys. Authenticate with Application Default Credentials or run it from an identity-enabled Google Cloud environment.

To make the API prefer BigQuery:

```powershell
$env:ECOTWIN_DATA_MODE = "auto"
$env:ECOTWIN_GCP_PROJECT = "YOUR_PROJECT_ID"
$env:ECOTWIN_BIGQUERY_DATASET = "ecotwin_demo"
```

Use `ECOTWIN_DATA_MODE=bigquery` only when startup should fail rather than fall back.

## Docker

```powershell
docker build -t ecotwin .
docker run --rm -p 8080:8080 -e ECOTWIN_DATA_MODE=local ecotwin
```

## Documentation

- [Checkpoint 2 implementation plan](ECOTWIN_CHECKPOINT2_PLAN.md)
- [Foundation architecture](docs/architecture.md)
- [Digital twin methodology](docs/digital-twin.md)
- [Waste detection methodology](docs/waste-detection.md)
- [What-if simulation methodology](docs/simulation.md)
- [Gemini explanation and safety contract](docs/gemini-explanation.md)
- [Google Cloud and BigQuery evidence](docs/evidence/cloud-foundation.md)
- [Cloud Run deployment evidence](docs/evidence/cloud-run-deployment.md)
- [Checkpoint 2 submission copy](docs/submission/checkpoint2-submission.md)
- [Timed demo script](docs/submission/demo-script.md)
- [Submission checklist](docs/submission/submission-checklist.md)
- [Screenshot and evidence index](docs/submission/evidence-index.md)

## Data integrity and security

- All JSON is validated with strict Pydantic models.
- Telemetry and dependency references must point to an existing resource.
- BigQuery identifiers are validated.
- Local fallback is visible to the user rather than silently impersonating cloud data.
- Secrets, service-account files and environment files are excluded from Git and Docker context.
- There are no cloud mutation endpoints.
