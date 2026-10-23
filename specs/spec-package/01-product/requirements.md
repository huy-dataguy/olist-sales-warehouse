# Product requirements

## Goal

A local Sales & Customer Analytics Warehouse with enterprise engineering controls: reliable business metrics, Kimball dimensional integration, executable semantics, reproducible operation and recovery.

Current scope is a working local demo. The user explicitly defers production expansion and requests Superset dashboards with question-driven, reproducible analysis. Runtime acceptance remains bounded by recorded results.

## Consumers and use cases

Business overview, product/seller performance, read-only analysis, data operations and interview reproduction. See ../02-architecture/consumer-workload-map.md.

## Non-goals

- Telesales/NHS/clinical data or claimed Abbott/Concentrix internal architecture.
- Marketing Funnel, reviews, geolocation analytics, MPP, Kafka, Spark and Kubernetes in the selected workload.
- Paid dbt cloud dependency, native source CDC, inferred historical status/effectivity or invented attributes.
- Product/seller payment allocation or product-level AOV without a separate business definition.
- Multi-host HA or a 24/7 cluster SLA on a single personal machine.
- Production rollout or enterprise certification beyond the verified local demo.

## Risk: medium

Licensed bounded data and non-mutating design verification now. Future schema/security/restore work has controlled migration/isolation gates; no destructive reset of an existing environment is implied.

## Requirements

### REQ-001 - Reproducible source data

Acceptance criteria:

- The original source has checksum, provenance, license, feed inventory, null/key profiles and independently computed baseline. Verify: V-001.
- Real-source data and every synthetic operational/effectivity scenario remain explicitly separated. Verify: V-001 and V-014.

Risk: medium
Depends: none

### REQ-002 - Auditable immutable raw

Acceptance criteria:

- Actual object storage preserves source bytes and manifest/receipt identity; re-delivery cannot overwrite a different payload. Verify: V-002.
- Unknown schema leaves preserved raw and an observable failed admission. Verify: V-002 and V-010.

Risk: medium
Depends: REQ-001

### REQ-003 - Transactional incremental admission

Acceptance criteria:

- Seven feeds admit accepted source versions under explicit revision/key contracts and a committed source boundary; replay causes no extra business versions. Verify: V-003 and V-018.
- Occurrence accounting, conflict/quarantine policy and checkpoint transaction are observable. Verify: V-003 and V-007.

Risk: high
Depends: REQ-002 and REQ-015

### REQ-004 - Correct dimensional Warehouse

Acceptance criteria:

- Three fact grains retain accepted source coverage and reconcile to source money/counts without fact-to-fact fanout. Verify: V-004 and V-013.
- Full-source delivered orders = 96478, delivered merchandise value = 13221498.11 and delivered distinct customers = 93358. Verify: V-004.

Risk: medium
Depends: REQ-003 and REQ-013 and REQ-018

### REQ-005 - Executable governed semantic models

Acceptance criteria:

- Local MetricFlow executes PostgreSQL queries with conformed entities, allowed dimensions and explicit release binding, without paid cloud dependency. Verify: V-005 and V-017.
- Totals/groupings/ratios/distincts match independent SQL and golden expectations; unsupported dimensions and denominator-zero behavior are verified. Verify: V-005.

Risk: medium
Depends: REQ-004 and REQ-017

### REQ-006 - Consistent business dashboards

Acceptance criteria:

- An executive entry dashboard links to five specialist Superset pages answering sales, commercial, customer, delivery/payment and data-trust questions; business charts share one retained published release and operational charts declare their context. Verify: V-006 and V-017.
- Monthly distinct customers and ratio KPIs match MetricFlow and independent SQL; new publication cannot mix browser card versions. Verify: V-006.
- A reproducible analysis report links computed findings to versioned SQL, exact release/cutoff, denominator and source limitations; customer/cohort/payment measures preserve their declared grains. Verify: V-006.
- Every report presents concise business context, KPIs and computed findings with period/denominator and follow-up. Purpose, definitions and limitations remain available in chart descriptions and documentation, not repeated long introduction/instruction/disclaimer panels. Technical release/source-cut details belong on the data-trust page. Monthly findings change with the selected month; missing comparison bases are explicit, not fabricated zero changes. Verify: V-006.
- In-dashboard overview/back/sibling links preserve published release and selected navigation month. Overview/sales/commercial/service findings use that month; customer cutoff and trust producer remain explicitly fixed even when navigation month changes. Rebootstrap does not duplicate assets. Verify: V-006.

Risk: medium
Depends: REQ-005 and REQ-008

### REQ-007 - Source-aware quality and reconciliation

Acceptance criteria:

- Schema/key/grain/transformation defects block promotion; known source null/coverage/payment differences are reported without fabricated repairs. Verify: V-007.
- Full source reports 775 orders without items, 1 without payments, 8 delivered orders without delivery timestamp and 303 matched orders with payment delta above 0.01. Verify: V-007.
- Received occurrences reconcile to accepted, duplicate and rejected occurrences; current distinct entity counts are reported separately. Verify: V-007.

Risk: medium
Depends: REQ-004

### REQ-008 - Observable reliable orchestration

Acceptance criteria:

- Airflow runs stage dependencies, bounded retries/timeouts, structured IDs/logs and accurate failed task/DAG state. Verify: V-008.
- Validation/export failure cannot promote; lost acknowledgement after valid commit is resolved idempotently. Verify: V-008 and V-010 and V-017.

Risk: medium
Depends: REQ-005 and REQ-007 and REQ-017

### REQ-009 - Replay and correction equivalence

Acceptance criteria:

- Initial/next/repeated batch, late child and explicitly versioned correction are reproducible scenarios. Verify: V-009.
- Incremental and full rebuild of the same accepted artifact/revision set have equal logical facts and KPIs; a retained registry does not reassign dimension SKs. Verify: V-009.

Risk: medium
Depends: REQ-008 and REQ-018

### REQ-010 - Failure recovery

Acceptance criteria:

- Injected failures after raw/load/build/snapshot/export and before publication preserve the last valid consumer release and leave complete diagnostics. Verify: V-010.
- Schema drift, retry and acknowledgement loss recover without duplicate keys or false success. Verify: V-010.

Risk: medium
Depends: REQ-008 and REQ-009

### REQ-011 - Measured SQL performance

Acceptance criteria:

- A representative query has reproducible plans/timings/buffers before and after a justified change on equal results and recorded cache/run conditions. Verify: V-011.
- No speedup or response-time SLO is claimed without measured evidence. Verify: V-011 and V-020.

Risk: medium
Depends: REQ-004

### REQ-012 - Reproducible local product handoff

Acceptance criteria:

- Pinned services run real source -> Warehouse -> semantic -> BI end to end and all required runtime gates pass. Verify: V-012.
- Handoff includes contracts, Kimball design, lineage, source/metric definitions, locks, runbooks, backup/restore/security and measured capacity within 70 GB. Verify: V-012 and V-015 and V-016 and V-019 and V-020.

Risk: medium
Depends: REQ-006 and REQ-010 and REQ-011 and REQ-014 and REQ-015 and REQ-016 and REQ-019 and REQ-020

### REQ-013 - Kimball conformance

Acceptance criteria:

- Bus matrix, declared process/grain, seven conformed dimensions, warehouse-managed integer SK registry, unknown/inferred members and role dates are implemented and validated. Verify: V-013.
- Applicable fact keys resolve within the same release; registry keys survive replay/rebuild; accumulating snapshot and measure additivity rules match the design. Verify: V-013.

Risk: medium
Depends: REQ-003

### REQ-014 - Effectivity and late-arriving dimension correctness

Acceptance criteria:

- Explicit-effectivity fixtures prove Type 2 non-overlap/current uniqueness, unchanged-payload no-op, late interval split and exact-boundary lookup. Verify: V-014.
- Inferred-member enrichment preserves its key; unknown history does not select the latest version; real Olist snapshot is not assigned fabricated historical versions. Verify: V-014.

Risk: medium
Depends: REQ-013

### REQ-015 - Security and secrets

Acceptance criteria:

- Separated roles allow required operations and deny unauthorized raw/work/candidate/publication/DDL access; UI bindings and secrets follow the declared boundary. Verify: V-015.
- Credentials rotate with old credential denial; logs/evidence/config contain no plaintext secrets. Verify: V-015.

Risk: high
Depends: REQ-002

### REQ-016 - Backup, restore and rollback

Acceptance criteria:

- Checksummed consistent backups contain source/version state, registry, validated releases and pointer with migration/lock metadata. Verify: V-016.
- Restore into an isolated target verifies keys/KPIs/roles/release integrity and measures RPO/RTO; rollback selects a retained validated release without modifying active source. Verify: V-016.

Risk: high
Depends: REQ-008 and REQ-017

### REQ-017 - Whole-release consistency and fencing

Acceptance criteria:

- Immutable consumer dimensions/facts and metric exports share source-cut/contract/release identity; a final transaction publishes only complete validated output. Verify: V-017.
- Missing/wrong semantic binding, stale lease owner, competing publishers and a browser refresh cannot expose mixed/unpublished data. Verify: V-017.

Risk: high
Depends: REQ-004 and REQ-007 and REQ-018

### REQ-018 - Consistent source versions and checkpoints

Acceptance criteria:

- All model reads at source_cut use the same accepted committed input set; commit ordering is protected by admission control, not assumed from sequence allocation. Verify: V-018.
- Per-model checkpoints, late/revised parent-child changes and fenced shared-work retries produce deterministic recoverable state. Verify: V-018 and V-009.

Risk: medium
Depends: REQ-003

### REQ-019 - CI and change governance

Acceptance criteria:

- Automated gates validate spec/contracts, golden data, offline semantic compatibility and isolated integration behavior with archived evidence. Verify: V-019.
- Breaking schema/metric changes have reviewed ADR/impact/migration/backfill/consumer plans; admitted runbooks are real and dependency/image locks are reproducible. Verify: V-019.

Risk: medium
Depends: REQ-008 and REQ-014 and REQ-015

### REQ-020 - Operational service objectives and capacity

Acceptance criteria:

- Freshness, quality, publication lag, lease health, query latency, connection/WAL pressure and disk budget are observable against declared operating windows. Verify: V-020.
- SLO/RPO/RTO/capacity targets are measured, retention protects referenced data and runbooks cover startup, failure, resume, rotation and restore. Verify: V-020.

Risk: medium
Depends: REQ-008 and REQ-011 and REQ-016

## Decisions

Airflow, dbt Core/PostgreSQL and executable semantic models/MetricFlow remain mandatory. Olist's seven commerce feeds are the real source. Kimball conformed dimensions and integer SKs, immutable full consumer releases, source-cut consistency, role separation, backup/restore and release-pinned BI form the baseline. The user's subsequent demo-only decision replaces Metabase with Superset plus governed business analysis (ADR-014), without expanding to production operations.

Select Type 0/1/2 from business semantics and source reality. Type 2 capability is validated with explicit synthetic effectivity; no history is invented for Olist.

## Open issues

Implementation spikes and external business unknowns are recorded in docs/implementation-readiness.md. Exact container digests, MinIO source build, adapter release-setting propagation, real performance/resource and restore measurements remain runtime gates. The full JD/product domain is not assumed.

