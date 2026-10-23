# System architecture

## Scope and design authority

Design baseline with implemented local-demo scope. ADR-014 records the user's subsequent Superset reporting/analysis revision; production expansion is deferred.

[Production architecture](production-local.md) is the authoritative consistency/storage/concurrency design.
[Kimball model](../03-data/kimball-design.md) defines grains, conforming dimensions and keys.
[Security/governance](security-and-governance.md) and [operating model](../08-operations/operating-model.md) define the operational boundaries.

## Data and control path

Original Olist -> Python contracts/raw capture -> accepted source versions -> fixed source_cut -> dbt working models -> quality/Kimball gates -> immutable Warehouse snapshot -> release-bound MetricFlow -> exports/parity -> fenced publication -> pinned Superset consumption. Extended analysis uses published-only SQL views with declared order/customer/payment/cohort grains; never atomic fact-to-fact metric joins.

Airflow controls dependencies/retries/status. dbt controls SQL/model dependencies and tests. MetricFlow owns metric computation from semantic definitions. None replaces the others.

## Responsibilities

| Component | Owns | Failure boundary |
|---|---|---|
| Ingestion | Capture, wire/normalized contracts, receipts, accepted revisions/quarantine | No invalid admission; preserved raw remains inspectable |
| MinIO | Immutable raw content | No load success when required raw cannot be preserved |
| PostgreSQL | Version ledger, key registry, work/candidate/published stores and transactional ops | Commit consistent state; preserve prior release |
| dbt | Staging, intermediate, seven dimensions, three facts, quality, docs | Failed model/test blocks snapshot/promotion |
| Snapshot service | Typed immutable dimension/fact copies at one cut/release | Incomplete copy stays invisible |
| MetricFlow/exporter | Declared metrics, legal dimensions, release-bound generated SQL/results | Query/binding/parity failure blocks publication |
| Publisher | Fence/required-check validation and one pointer transaction | Reject stale or incomplete candidates |
| Airflow | Stage task states, bounded retries/timeouts, run linkage | Upstream failure cannot be hidden by notification |
| Superset | Release-specific virtual datasets, dashboards, native month filters, saved SQL analysis | Prior assets stay pinned when publication changes; extended metrics have SQL/oracle contracts |

## DAG contract

check_source -> preserve_raw -> validate_contracts -> admit_source_versions -> freeze_source_cut -> dbt_build_work -> warehouse_quality -> freeze_warehouse_snapshot -> semantic_validate -> metric_export -> metric_parity -> publish_release.

Lifecycle/error paths, lease renewals and per-stage inputs/outputs are in production-local.md and operations. XCom carries small identifiers/paths/counts, not datasets.

## Physical local deployment

One host, PostgreSQL with separate databases/users for Warehouse, Airflow and Superset metadata; MinIO; Airflow LocalExecutor; isolated dbt/MetricFlow interpreter; Superset 6.1.0. Historical Metabase metadata is retained. UI binds to loopback and internal services use private networks. Images are pinned in infra files.

Semantic compatibility has a pinned, tested offline combination: Python 3.12, dbt-core 1.12.6, dbt-postgres 1.11.0, dbt-metricflow 0.15.0, metricflow 0.213.0.

Planned families: Airflow 3.x, PostgreSQL 17, Metabase OSS. MinIO source revision 7aac2a2c5b7c882e68c1ce017d8256be2feea27f; source build/startup/S3 gate required because community upstream is unmaintained/source-only. Exact image digests require runtime foundation evidence.

## Existing enterprise DWH adaptation

This is a locally provisioned reference design with integration into a controlled target. A real engagement confirms its DWH dialect, identity/contract, access and workload before adapting connectors/adapters. No company stack is inferred from Olist.

