# What-if simulation methodology

EcoTwin's `simulation-v1.0` engine calculates a read-only right-sizing scenario. Code calculates every number; a later Gemini module will only explain the returned JSON.

## Hero scenario

```text
Resource: vm-api-01
Current: e2-standard-4, 4 vCPU, 16 GB
Proposed: e2-standard-2, 2 vCPU, 8 GB
Runtime: 730 hours/month
Growth buffer: 20%
```

## Cost estimate

```text
compute cost = controlled hourly rate x runtime hours
storage cost = attached GB x controlled storage rate
monthly total = compute cost + unchanged attached storage cost
```

The controlled rates are versioned scenario assumptions, not a live price quote or invoice forecast.

For the hero scenario:

| Metric | Before | After | Impact |
|---|---:|---:|---:|
| Compute cost | $97.82 | $48.91 | -$48.91 |
| Attached storage | $5.00 | $5.00 | $0.00 |
| Monthly total | $102.82 | $53.91 | 47.6% savings |

## Estimated operational carbon

The average compute-power proxy is:

```text
CPU kW = vCPU x (0.004 idle kW/vCPU + 0.012 dynamic kW/vCPU x CPU mean fraction)
memory kW = memory GB x 0.000375 kW/GB
estimated kWh = (CPU kW + memory kW) x runtime hours x PUE
estimated kgCO2e = estimated kWh x regional gCO2e/kWh / 1000
```

For `us-central1`, the controlled factor is 394 gCO2e/kWh and PUE is 1.1. The hero result is 9.583 kgCO2e before and 6.627 kgCO2e after: an estimated reduction of 2.956 kgCO2e, or 30.8%.

This is an engineering estimate of operational carbon. It is not Google's official customer Carbon Footprint value and excludes embodied emissions and storage energy.

## Performance proxy

```text
predicted CPU = current CPU x current vCPU / proposed vCPU x growth multiplier
predicted memory = current memory p95 x current GB / proposed GB x growth multiplier
headroom = 100 - predicted utilization
```

The 20% growth-buffer scenario projects CPU p95 from 34% to 81.6% and memory p95 from 48% to 100%. This is a capacity proxy, not a load test.

## Risk and confidence

Risk can only increase as evidence becomes more concerning:

- Low: predicted CPU p95 at or below 65%, memory headroom at least 25%, and sufficient evidence.
- Medium: CPU p95 between 65% and 80% or memory headroom below 25%.
- High: CPU p95 above 80%, memory p95 above 90%, fewer than seven samples, or a high-criticality node with multiple dependencies.

The hero scenario is `HIGH` risk. That is intentional: EcoTwin exposes an attractive cost/carbon saving but warns that applying it directly would be unsafe.

Confidence is `MEDIUM` because the controlled evidence window contains seven complete days. Fourteen or more complete days are required for high confidence.

## Determinism and auditability

The simulation ID hashes the snapshot ID, normalized request and method version. The same request against the same twin snapshot produces the same ID and numeric result. The response also includes data version, price/carbon sources, effective dates and all assumptions.

The engine creates no resize, stop or delete request against Google Cloud.
