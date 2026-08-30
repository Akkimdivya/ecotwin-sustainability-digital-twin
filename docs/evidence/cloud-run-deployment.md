# Cloud Run deployment evidence

**Verified:** August 30, 2026 (IST)

## Production service

- Public application: <https://ecotwin-1075889318331.us-central1.run.app>
- Google Cloud project: `ecotwin-sustainability-2026`
- Region: `us-central1`
- Cloud Run service: `ecotwin`
- Ready revision: `ecotwin-00006-kch`
- Git commit deployed: `75ac021`
- Traffic: 100% to the ready revision
- Public access: `allUsers` has only `roles/run.invoker` on the service

The production container was built from the repository Dockerfile through Cloud Build and stored in the regional `cloud-run-source-deploy` Artifact Registry repository. The verified revision was produced by Cloud Build `a477711d-187c-4c35-a7e6-e5b9e1219f79`.

## Runtime controls

- Service account: `ecotwin-runtime@ecotwin-sustainability-2026.iam.gserviceaccount.com`
- Runtime IAM roles: `roles/bigquery.dataViewer`, `roles/bigquery.jobUser`, `roles/aiplatform.user`
- API keys: none
- Service-account key files: none
- Authentication: Application Default Credentials supplied by Cloud Run
- CPU: 1
- Memory: 512 MiB
- Concurrency: 40
- Request timeout: 60 seconds
- Service-level scaling: 0 minimum, 2 maximum instances

The service account has no Owner, Editor, BigQuery Admin or Vertex AI Admin role. The project contains only the controlled EcoTwin checkpoint dataset, so project-level data viewer access is bounded to the demo project.

## Live API verification

The public health endpoint returned:

```json
{"status":"ok","service":"ecotwin-api","version":"0.1.0","data_mode":"bigquery"}
```

The data-status endpoint confirmed live BigQuery with no fallback:

```json
{"requested_mode":"bigquery","active_mode":"bigquery","display_source":"CONTROLLED_DEMO","data_version":"demo-2026-08-27-v1","resource_count":9,"fallback_reason":null}
```

The AI-status endpoint confirmed Vertex AI through ADC:

```json
{"enabled":true,"mode":"VERTEX_AI","model":"gemini-2.5-flash","location":"global","authentication":"APPLICATION_DEFAULT_CREDENTIALS","api_key_required":false}
```

## End-to-end hero-flow verification

The public browser completed:

> Cloud Data -> Digital Twin -> Detect Waste -> Select Recommendation -> Simulate -> Cost + Carbon + Performance + Risk -> Gemini Explanation

For the controlled `vm-api-01` scenario, 4 vCPU/16 GB was compared with 2 vCPU/8 GB. The application returned simulation `sim-6db42a0b799b9c24` with:

- monthly cost: `$102.82` to `$53.91`;
- monthly savings: `$48.91` (`47.6%`);
- estimated operational carbon: `9.583` to `6.627 kgCO2e`;
- estimated carbon reduction: `2.956 kgCO2e` (`30.8%`);
- projected CPU p95: `81.6%`;
- projected memory p95: `100.0%`;
- risk: `HIGH`;
- explanation provider: `VERTEX_AI`;
- model: `gemini-2.5-flash`;
- fallback reason: `null`.

Gemini preserved the engine values and warned: do not implement the recommendation directly because predicted pressure and dependency criticality make it high risk. The UI also displayed validation steps and a rollback trigger.

## Resilience verification

Before production verification, a deliberately constrained model response was truncated. Pydantic rejected it and EcoTwin returned its deterministic fallback with the exact engine values, proving that an invalid model response cannot break the demo or replace calculated numbers. The generation configuration was then corrected for predictable explanation-only output, tested directly through Vertex AI, deployed as revision 3 and re-verified through the public endpoint.
