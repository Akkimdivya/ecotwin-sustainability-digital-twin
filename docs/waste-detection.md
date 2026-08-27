# Waste detection methodology

EcoTwin's Checkpoint 2 detectors are deterministic rules, not model guesses. Every finding includes its rule ID, evidence window, observed values, thresholds, proposed action, confidence, limitations and simulation eligibility.

## Method version

`waste-rules-v1.0`

The method version and all thresholds are returned by `GET /api/findings` so results remain auditable.

## Detectors

### Idle compute

Requires at least seven complete telemetry days and all three strict comparisons:

```text
CPU mean < 5%
CPU p95 < 10%
mean network < 0.25 GB/day
```

Proposed action: simulate scheduled shutdown, then verify ownership and workload timing.

### Over-provisioned compute

Requires at least seven complete days, must not meet the idle rule, and uses strict comparisons:

```text
CPU p95 < 40%
memory p95 < 60%
```

Proposed action: simulate one machine size smaller while preserving at least 20% projected headroom.

### Storage waste

```text
persistent disk is unattached
unattached duration >= 7 days
```

Proposed action: simulate deletion only after backup, retention and ownership validation.

## Controlled-data results

| Resource | Finding | Key evidence | Confidence |
|---|---|---|---|
| `vm-batch-02` | Idle compute | 7 days, CPU mean 2.06%, CPU p95 5.2%, network 0.17 GB/day | High |
| `vm-api-01` | Right-sizing candidate | 7 days, CPU p95 34%, memory p95 48%, current 4 vCPU | High |
| `disk-orphan-01` | Storage waste | 200 GB disk unattached for 21 days | High |

## Boundary validation

Automated tests prove that 5% CPU mean and 10% CPU p95 do not pass the idle detector, while values just below them do. The same tests prove that 40% CPU p95 and 60% memory p95 do not pass the over-provisioning detector. These cases prevent ambiguous inclusive/exclusive threshold behavior.

## Safety

Findings are recommendations only. EcoTwin does not stop, resize or delete resources. Each card tells the user to validate ownership, workload behavior, backups or rollback requirements before a real change.
