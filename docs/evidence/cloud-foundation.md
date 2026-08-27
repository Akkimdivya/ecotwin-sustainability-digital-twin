# Google Cloud foundation evidence

**Verified:** August 27-28, 2026 (IST)
**Project:** `ecotwin-sustainability-2026`  
**Project number:** `1075889318331`  
**Region/location:** `us-central1`  
**Dataset:** `ecotwin_demo`  
**Data version:** `demo-2026-08-27-v1`

## Scope completed

- Created a dedicated Google Cloud project under the approved Chrome profile.
- Enabled BigQuery, Cloud Run, Cloud Build, Artifact Registry, Vertex AI, IAM and Service Usage APIs.
- Uploaded only the curated source/data bootstrap archive to Cloud Shell.
- Validated every controlled-data row before cloud mutation.
- Created the BigQuery dataset and seven tables.
- Verified the backend repository and HTTP APIs against live BigQuery data.
- Created no API keys and downloaded no service-account credentials.
- Verified a structured `gemini-2.5-flash` request through Vertex AI and ADC in the approved Cloud Shell session.

## Vertex AI verification

On August 28, 2026, a read-only structured-output smoke test called `gemini-2.5-flash` through Vertex AI in location `global`. It used the signed-in Cloud Shell identity through Application Default Credentials and returned:

```json
{"status":"VERIFIED","message":"Read-only EcoTwin explanation test confirmed."}
```

No API key or service-account key file was created. The application additionally includes a deterministic fallback so the demonstration completes if Vertex AI is temporarily unavailable.

## BigQuery tables

| Table | Rows | Storage design |
|---|---:|---|
| `metadata` | 1 | Dataset/data-version record |
| `resources` | 9 | Clustered by `service_type`, `region` |
| `telemetry_daily` | 32 | Partitioned by `date`, clustered by `resource_id` |
| `dependencies` | 7 | Digital-twin relationship edges |
| `price_cards` | 6 | Clustered by `service_type`, `region` |
| `carbon_factors` | 3 | Regional controlled factors |
| `simulation_runs` | 0 | Partitioned by `created_at`; ready for later simulations |

## Live verification results

The BigQuery repository returned:

```text
active_mode: bigquery
data_version: demo-2026-08-27-v1
resources: 9
telemetry: 32
dependencies: 7
price_cards: 6
carbon_factors: 3
```

The FastAPI smoke test returned:

```json
{"status":"ok","service":"ecotwin-api","version":"0.1.0","data_mode":"bigquery"}
{"requested_mode":"bigquery","active_mode":"bigquery","display_source":"CONTROLLED_DEMO","data_version":"demo-2026-08-27-v1","resource_count":9,"fallback_reason":null}
```

## Reproduction

From an authenticated Google Cloud Shell session:

```bash
cd backend
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python -m scripts.validate_data
python -m scripts.load_bigquery \
  --project ecotwin-sustainability-2026 \
  --dataset ecotwin_demo \
  --location us-central1
python -m scripts.load_bigquery \
  --project ecotwin-sustainability-2026 \
  --dataset ecotwin_demo \
  --location us-central1 \
  --apply
```

The first loader command is a dry run. Only `--apply` writes to BigQuery.

## Data and safety statement

The Checkpoint 2 dataset is synthetic, controlled and visibly labeled `CONTROLLED_DEMO`. Cost and carbon values are scenario assumptions with effective dates and source URLs; they are not presented as invoices or measured emissions. EcoTwin's APIs are read-only at this stage, so the prototype cannot stop, resize or delete cloud resources.
