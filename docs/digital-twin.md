# Digital twin methodology

EcoTwin converts the normalized resource catalog into a deterministic, read-only topology snapshot. The snapshot is the stable input for later detector and simulation modules.

## API contract

`GET /api/twin` returns:

- A deterministic `snapshot_id` derived from the data version, observation time, nodes and edges.
- The snapshot timestamp and visible data-source label.
- Normalized nodes with provider configuration, telemetry summaries and connection counts.
- Validated dependency edges.
- Counts by node state.

`GET /api/twin/nodes/{resource_id}` returns the selected node plus its incoming and outgoing edges. Unknown resources return HTTP 404.

## Topology guarantees

- Every edge endpoint is validated against the normalized inventory before a snapshot is built.
- Nodes and edges are sorted before hashing, making the same input produce the same snapshot ID.
- Snapshot models are frozen to prevent accidental field replacement during a later simulation.
- The UI displays the snapshot and data versions so a result can be reproduced.

## Current node-state projection

Module 3 adds state projection so topology colors are useful before the dedicated recommendation engine is connected:

- `idle`: seven complete telemetry days, CPU mean below 5%, CPU p95 below 10%, and mean network below 0.25 GB/day.
- `over_provisioned`: seven complete days, CPU p95 below 40%, memory p95 below 60%, and not idle.
- `storage_waste`: persistent disk unattached for at least seven days.
- `healthy`: the current evidence does not meet a review threshold.
- `unassessed`: insufficient samples or no applicable rule.

The next module will turn these states into formal findings containing detector IDs, severities, evidence, confidence, proposed actions and simulation eligibility.

## Acceptance evidence

- 9 rendered nodes and 7 validated edges.
- Meaningful routes, disk attachments, database traffic and archive-storage dependencies.
- Selecting a node exposes configuration, seven-day telemetry and connected resources.
- Keyboard-selectable SVG nodes and a responsive details panel.
- Deterministic state checks for the controlled idle VM, right-sizing VM and orphan disk.
