# Operations summary

Authoritative details: [operating-model.md](operating-model.md).
Architecture/recovery transaction boundaries: [production-local](../02-architecture/production-local.md).
Machine scenarios: contracts/operational-scenarios.json and contracts/state-machines.json.

Current task is design-only. No service startup, scheduled pipeline, restore or production-readiness result is claimed.

## Required operational capabilities

Startup/health, initial and incremental admission, replay/resume, correction, publication rollback, backup, isolated timed restore, credential rotation, capacity/retention and incident handling.

Freshness measures actual acceptance/publication clocks, separately from historical source event dates. Prior immutable published output stays available through failed candidate processing.

Source warnings are visible; transformation defects fail. Failure after valid publication commit has an idempotent acknowledgement path. Restored leases/inflight owners are invalidated before enabling workers.

## Interview runbook contract

1. Show business questions, bus matrix and three fact grains.
2. Open business/commercial/health dashboards at one explicit release.
3. Trace a KPI through semantic SQL, frozen fact/dimension rows and source.
4. Demonstrate safe aggregation versus a multi-item/multi-payment fanout.
5. Replay a batch and compare results.
6. Show prepublish failure, stable prior output and successful recovery.
7. Show effectivity/inferred-member fixture, permission denial and restore evidence.
8. Explain measured resource/performance limits and the single-host boundary.

These demonstrations become accepted only after actual implementation/evidence. Offline design checks cannot replace the runtime steps.

