# Verification matrix

## Status and authority

This matrix records the original design acceptance contracts. Implementation was subsequently authorized on 2026-10-15. See [runtime coverage](../../../docs/implementation-progress.md) for commands/evidence that now exist and remaining gaps. `(planned)` below is the historical design status, not an assertion about current service state; do not infer all criteria passed from a similarly named make target.

## Executable now

- `make verify-spec`: package/reference/task-graph checks, not runtime proof.
- `make verify-contracts`: real-source wire schemas plus independent golden Kimball expectations and offline PostgreSQL DDL syntax.
- `make verify-semantic-offline`: representative parse, metric discovery, conformed-dimension SQL generation and illegal grouping rejection.
- `make verify-source`: full source profiling/baselines.
- `make verify-design`: spec + contracts + semantic-offline aggregate gate.

Evidence: docs/evidence/source-profile.json, design-contracts.json, semantic-probe.json, design-validation.json. A design check may support a requirement but cannot satisfy its service-dependent runtime acceptance alone.

## Runtime acceptance contracts

| Check | Requirement | Verify command | Required evidence |
|---|---|---|---|
| V-001 | REQ-001 | `python scripts/profile_source.py data/raw/olist/brazilian-ecommerce-v2.zip --output docs/evidence/source-profile.json` | Current real-source checksum, counts, nulls/keys and baseline |
| V-002 | REQ-002 | `make verify-raw` (planned) | Actual S3 PUT/GET hash, manifests/receipts, conflicting payload and source-loss behavior |
| V-003 | REQ-003 | `make verify-load` (planned) | Real version admission, transaction/checkpoint/precedence/replay and quarantine results |
| V-004 | REQ-004 | `make verify-warehouse` (planned) | Actual dbt build and source-to-fact counts/money/coverage at one cut |
| V-005 | REQ-005 | `make verify-semantic` (planned) | Real PostgreSQL MetricFlow totals/groupings/ratios/distincts/zero/forbidden dimensions and independent parity |
| V-006 | REQ-006 | `make verify-bi && make analyze && make verify-browser` | Executive entry + 5 specialist Superset pages, core MetricFlow parity, analysis/grain checks, computed commentary with SQL/numeric parity, missing-base handling, concise context/no repeated instructional panels, overview KPIs in first desktop viewport, full methodology in chart descriptions/docs, native month changes on all 4 monthly boards, actual forward/back/sibling navigation retaining release/month, fixed customer/trust scopes and idempotent assets; historical publication-transition evidence remains separately scoped |
| V-007 | REQ-007 | `make verify-quality` (planned) | Source warning baselines plus mandatory error rejection, FKs/grains and occurrence accounting |
| V-008 | REQ-008 | `make verify-orchestration` (planned) | Actual Airflow DAG/task/retry/timeouts and accurate failure state |
| V-009 | REQ-009 | `make verify-replay` (planned) | Same batch no-op; late/correction cases; full/incremental logical equivalence |
| V-010 | REQ-010 | `make verify-recovery` (planned) | Injected raw/load/dbt/snapshot/export/publish/ack failures and deterministic recovery |
| V-011 | REQ-011 | `make verify-performance` (planned) | Recorded plans/buffers/runs/cache and unchanged output |
| V-012 | REQ-012 | `make verify-boot && make verify-e2e` (planned) | Real source-to-pinned-BI plus complete required runtime gates and supported environment |
| V-013 | REQ-013 | `make verify-kimball` (planned) | Actual registry and 7-dimension/3-fact constraints, role dates, no fanout, additivity |
| V-014 | REQ-014 | `make verify-effectivity` (planned) | Real implementation matches explicit fixture: late SCD2, exact boundaries, inferred SK, no fabricated source history |
| V-015 | REQ-015 | `make verify-security` (planned) | Allowed/denied access paths, network boundary, rotation and redacted evidence |
| V-016 | REQ-016 | `make verify-restore` (planned) | Checksummed backup, isolated timed restore, key/KPI/role/pointer proof and safe rollback |
| V-017 | REQ-017 | `make verify-release-isolation` (planned) | Full snapshot/source-cut integrity; semantic binding; expired/concurrent fence; pinned browser release |
| V-018 | REQ-018 | `make verify-source-cuts` (planned) | Committed version boundary, no partial-batch visibility, model checkpoints and late-parent/child consistency |
| V-019 | REQ-019 | `make verify-ci` (planned) | Actual PR/isolated-integration/release gates, locks and reviewed schema/metric change process |
| V-020 | REQ-020 | `make verify-operations` (planned) | Measured freshness/query/resource/RPO/RTO goals, retention and incident/runbook checks |

All gates require actual command exit 0 and named results. Negative scenarios require the expected failure plus preserved invariants. Skipped/pending/failed checks are never pass.

DDL parse is grammar validation only, not provisioning/constraint/index/privilege proof. Golden fixtures are synthetic and separate from the real-source baseline. Offline MetricFlow does not prove PostgreSQL connection/release binding or result correctness.

No blanket certification of all gates or native DSH dossier admission is claimed. Individual runtime proofs are reported with their scope in the implementation coverage.

