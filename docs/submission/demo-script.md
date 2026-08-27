# EcoTwin Checkpoint 2 demo script

**Target duration:** 2 minutes 20 seconds  
**Demo URL:** <https://ecotwin-1075889318331.us-central1.run.app>

Keep the browser at 100% zoom. Close notifications and unrelated tabs. Start from a freshly loaded EcoTwin page so the result panel is empty.

## 0:00–0:15 — Problem and promise

**Screen:** Hero section and `CONTROLLED_DEMO / BIGQUERY` badge.

**Narration:**

> Cloud teams are pressured to reduce cost and carbon, but an optimization can create a performance incident. EcoTwin is a read-only sustainability digital twin that lets engineers see the impact before they change production.

## 0:15–0:35 — Cloud data and digital twin

**Screen:** Point to nine resources, seven dependencies and three review states. Move over the topology without opening unrelated panels.

**Narration:**

> This deployed Cloud Run application reads a controlled, versioned resource catalog from BigQuery. It builds a nine-node dependency graph, so every recommendation includes workload context and blast radius—not just an isolated utilization number.

## 0:35–0:55 — Explainable waste detection

**Screen:** Scroll to the three opportunity cards.

**Narration:**

> EcoTwin already detects the three required waste classes: idle compute, over-provisioned compute and unattached storage. Each finding shows its evidence, confidence and the exact rule version used.

Click **Simulate recommendation** on `api-vm-01`.

## 0:55–1:15 — What-if setup

**Screen:** Show current 4 vCPU/16 GB, proposed 2 vCPU/8 GB and 20% growth buffer.

**Narration:**

> Here the candidate changes from four to two vCPU and sixteen to eight gigabytes of memory. The simulation is read-only. No Google Cloud resource will be resized.

Click **Run what-if simulation**.

## 1:15–1:45 — Measurable impact and risk

**Screen:** Show the result cards, pressure bars and HIGH-risk reasons.

**Narration:**

> The deterministic engine estimates monthly cost falling from 102 dollars and 82 cents to 53 dollars and 91 cents—a 47.6% saving. Estimated operational carbon falls by 30.8%. But CPU p95 rises to 81.6%, memory reaches 100%, and this VM is highly connected. EcoTwin therefore marks the scenario HIGH risk.

Pause briefly on the red pressure bars.

## 1:45–2:10 — Gemini explanation

**Screen:** Show `Vertex AI / gemini-2.5-flash`, the recommendation, validation steps and rollback trigger.

**Narration:**

> Deterministic code calculates every number; Gemini only explains the signed simulation result. It correctly says not to implement this change directly, then gives staging, canary and dependency-validation steps plus a rollback trigger. Structured validation, retry, caching and a deterministic fallback make the demo resilient.

## 2:10–2:20 — Close

**Screen:** Keep the Gemini provider and rollback trigger visible.

**Narration:**

> EcoTwin helps cloud engineers optimize safely—not blindly. The live application, source code, architecture and validation evidence are all included in our Checkpoint 2 submission.

## Recording quality gate

- Record at 1080p or higher.
- Keep the mouse still while speaking about a result.
- Do not expose unrelated browser tabs, account menus, Cloud Console details or personal information.
- Show the `CONTROLLED_DEMO / BIGQUERY`, `HIGH risk` and `Vertex AI / gemini-2.5-flash` labels clearly.
- Do one uninterrupted take if possible; otherwise use only clean cuts between the sections above.
- Verify audio, text readability and the live URL before uploading.
