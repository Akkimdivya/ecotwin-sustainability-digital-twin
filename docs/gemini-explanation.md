# Gemini explanation and safety contract

EcoTwin uses Gemini only after the deterministic simulation engine has calculated cost, operational carbon, performance pressure, confidence and risk. The model explains the supplied result; it does not calculate or change those values.

## Runtime configuration

- Provider: Vertex AI through the Google Gen AI SDK (`google-genai`).
- Default model: `gemini-2.5-flash`, configurable with `ECOTWIN_GEMINI_MODEL`.
- Location: `global`, configurable with `ECOTWIN_GEMINI_LOCATION`.
- Authentication: Application Default Credentials (ADC). No frontend key, API key or downloaded service-account key is required.
- Enablement: `ECOTWIN_GEMINI_ENABLED=true`. The default is disabled so a local clone remains safe and predictable.

The implementation follows the official [Vertex AI quickstart](https://docs.cloud.google.com/vertex-ai/generative-ai/docs/start/quickstart), [Google Gen AI SDK guidance](https://cloud.google.com/vertex-ai/generative-ai/docs/sdks/overview), and [Python SDK structured-output API](https://googleapis.github.io/python-genai/index.html).

## Numerical-integrity contract

The system instruction requires Gemini to:

- use only the complete server-produced simulation JSON;
- preserve every numeric value exactly;
- make no claim that production infrastructure was changed;
- identify a high-risk scenario explicitly and avoid recommending direct implementation;
- return structured JSON rather than free-form prose.

Pydantic validates six output fields: `summary`, `recommendation`, `rationale`, `validation_steps`, `rollback_trigger`, and `limitations`. The response also records its provider, model, prompt version and generation time. Chain-of-thought is neither requested nor stored.

## Reliability behavior

Each Vertex AI request has a configurable 10-second timeout and one retry. A successful explanation is cached in memory by deterministic simulation ID. If Gemini is disabled, unconfigured, unavailable, times out or returns invalid output, EcoTwin returns a deterministic explanation containing the exact simulation values. The UI displays whether the response came from Vertex AI or the fallback.

## Verified example

The controlled `vm-api-01` scenario changes 4 vCPU to 2 vCPU. The deterministic engine estimates:

- monthly cost: `$102.82` to `$53.91`;
- monthly savings: `$48.91` (`47.6%`);
- estimated operational carbon: `9.583` to `6.627 kgCO2e`;
- estimated carbon reduction: `2.956 kgCO2e` (`30.8%`);
- projected CPU p95: `81.6%`;
- projected memory p95: `100.0%`;
- risk: `HIGH`.

The explanation therefore recommends validation or an intermediate configuration, never a direct production change. Tests prove exact-number fallback, structured response validation, retry behavior and caching.
