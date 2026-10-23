# Implementation plan

## Current handoff boundary

The user chose complete design/specs first, implementation later. No service or application pipeline is deployed in this turn. DDL under db/design/ is a syntax-checked review artifact, not an applied migration.

Task-graph requirements and dependencies are authoritative planning; they execute nothing.

## Phase gates

| Phase | Main work items | Outcome | Required gates |
|---|---|---|---|
| P0 - Design/data contracts | Existing design checks, TASK-001 planning inputs | Frozen source/fixture/Kimball/release/ops contracts and logical DDL | make verify-design; does not satisfy runtime requirements |
| P1 - Secure foundation | TASK-002,015,003 | Pinned services, actual raw store, least privilege, reviewed migrations and source ledger | V-002,003,015 |
| P2 - Versioned Kimball work | TASK-013,018,004,014,007 | Stable key registry, source-cut models, 7 dimensions/3 facts, effectivity cases and DQ | V-004,007,013,014,018 |
| P3 - Immutable serving and semantics | TASK-017,005 | Full Warehouse snapshot, fenced publisher, actual release-bound MetricFlow and parity | V-005,017 |
| P4 - Orchestration and BI | TASK-008,006 | Airflow stage behavior and 5 release-pinned Superset dashboards with computed commentary (ADR-014) | V-006,008 |
| P5 - Recovery/operations | TASK-009,010,011,016,019,020 | Rebuild/replay, failure recovery, security/CI, backup/restore and capacity/latency evidence | V-009,010,011,015,016,019,020 |
| P6 - Acceptance/handoff | TASK-012 | Reproducible source-to-consumer product and evidence bundle | V-012 plus all required runtime gates |

The task graph resolves exact prerequisite order within phases. TASK-015 provisions the reviewed source/ops/store schema and roles after raw-storage foundation, before TASK-003 attempts admission. TASK-013 implements registry-backed dimensions on that provisioned schema. This avoids requiring a loader/security check before its database exists. Build an initial real-data vertical slice, then full history; preserve every enterprise integrity boundary rather than creating placeholder components.

## Target implementation structure

- src/sales_dw/: adapters, raw/admission/versioning, key registry/effectivity, snapshot/semantic/export/publish, ops.
- contracts/: versioned machine data/model/metric/release/scenario/dashboard contracts.
- db/migrations/: reviewed provisioning for ops/registries/source ledger, store/views, roles/indexes.
- dbt/: source-at-cut staging, intermediate, dimensions/facts, quality, semantic inputs/models/tests/docs.
- orchestration/dags/: Airflow DAG and small-ID XCom contracts.
- infra/: pinned Compose profiles, resource/network/secrets policy and S3 source build.
- bi/: reproducible dashboard definitions with mandatory release binding.
- tests/: independent fixtures plus unit/contract/integration/failure/security/restore cases.
- scripts/: controlled migrations and evidence-producing runtime verify/runbooks.
- docs/: operator/consumer/demo handoff, schema/metric change history and evidence.

## Required implementation spikes

See docs/implementation-readiness.md: MinIO source build; adapter session release binding; integer registry behavior; same-release PK/FKs; lease expiry/concurrency; BI pinned cards; exact images; timed restore/resources.

Resolve a failed spike with an ADR and contract/test updates before dependent implementation. Do not silently replace the semantic engine or omit restore/security gates.

## Schema safety and executable admission

Prepare migrations and rollback/backup implications before applying through the controlled entrypoint and applicable human gate. Do not execute DDL via diagnostics or reset the active environment to recover a test.

Only after real runbooks exist: validate the current requirement/task graph through the DSH integration, fill a bounded dossier.json and admit that slice. Design make targets do not imply runtime acceptance.

