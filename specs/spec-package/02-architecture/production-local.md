# Production-local architecture and consistency

## Scope and precedence

This is the expanded architecture baseline requested on 2026-10-15. It extends the initial export-only publication design to full consumer Warehouse + semantic + reporting consistency. Implementation is deferred by the user's explicit choice.

Single host: PostgreSQL, S3-compatible raw storage, Airflow, isolated Python/dbt/MetricFlow runtime, Metabase. Separate metadata/application databases and least-privilege roles. No Kafka/Spark/Kubernetes/MPP or redundant serving engine without a new workload.

## Logical storage boundaries

| Boundary | Purpose / authority | Mutable? | Consumer access |
|---|---|---|---|
| raw objects + artifact manifest | Original source bytes and capture identity | Append-only | Ingestion/operator only |
| landing/source_versions | Accepted observed versions with source/batch provenance | Append-only versions | Transformation service |
| landing/current_at_cut | Latest accepted version at an explicit source_cut | Derived view | dbt working target |
| work dimensions/facts | Incremental working state and model checkpoints | Rebuildable | Transformation/validation only |
| warehouse_store dimensions/facts | Frozen, typed copies tagged release_id | Immutable until governed retention | Publisher/semantic service |
| semantic_input views | One explicit candidate/published release for MetricFlow | Static views selecting a session release | Semantic service only |
| warehouse presentation views | Current validated dimensions/facts | Pointer-selected | Read-only analyst |
| reporting exports | MetricFlow-generated result sets tagged release_id | Immutable until retention | Read-only BI through validated views |
| ops metadata | Runs, states, leases, lineage, quality, publication | Controlled transitions | Scoped services; redacted health views |

Do not grant BI access to landing/work/ops credentials. Warehouse analyst views for a single SQL statement use one MVCC snapshot; multi-query consumers must pin a release or use REPEATABLE READ.

## Identifiers and clocks

artifact_id = cryptographic content identity.
batch_id = source artifact + declared deterministic selection/revision contract.
receipt_id = each delivery attempt.
pipeline_run_id = orchestration attempt/workflow identity.
source_cut = monotonically increasing accepted capture boundary.
release_id = immutable business data/model/metric release identity.
contract_version/model_version/semantic_manifest_hash/export SQL hashes link every result to meaning.

Source event/effectivity timestamps and actual received/published UTC clocks are different fields. Do not manufacture source_updated_at.

## Lifecycle and transaction boundaries

1. Verify archive availability/size/hash, preserve raw and register artifact receipt.
2. Validate schema and rows. Preserve rejected occurrences with reasons. Unknown schema or zero-tolerance mandatory-field rejection blocks admission.
3. In one load transaction append newly accepted source versions, record key/revision decisions and mark batch loaded. Duplicate receipt can grow audit counts but not accepted business state.
4. Acquire the transform/publish lease and freeze source_cut. All dbt source reads use that cut; every model has its own successful cut/checkpoint.
5. Build working dimensions/facts; validate the complete model graph. Same-cut retry is deterministic even if earlier models committed.
6. In a consistent transaction snapshot all consumer dimensions/facts into warehouse_store under the new release_id. Verify copy counts/hash totals and dimension relationships within that release.
7. Query MetricFlow through semantic_input at that explicit release_id; export fixed requests and compare independent SQL/golden expectations.
8. In one final transaction mark the release validated and advance the published pointer. An invalid, incomplete, stale-fenced or failed-check release cannot publish.
9. Publish the release-pinned dashboard URL and a durable audit summary. A lost acknowledgement after commit is resolved by an idempotent lookup of the already published release.

Raw upload + DB load are not a distributed transaction. State transitions preserve raw orphan receipts and allow safe retry; do not claim exactly-once transport.

## Source version precedence

Every accepted change records source namespace, entity, natural key, payload hash, original artifact/member/row, source revision provenance and capture sequence.

Equal revision / same hash: replay no-op.
Equal revision / different hash: conflict, quarantine and fail.
Older explicit source revision: retain receipt/diagnostic without replacing current accepted state.
Newer valid explicit revision: append new accepted version.
Unversioned published Olist input: only its declared snapshot version; operational corrections require a separate simulated namespace/contract.

current_at_cut resolves precedence among accepted versions no later than source_cut. It must not be a view of an unbounded mutable upsert table while models run.

## Concurrency and fencing

Airflow max_active_runs=1 is a first guard, not the sole integrity mechanism. ops.pipeline_leases stores owner run, expiry, heartbeat and a monotonically increasing fencing token.

Every stage that changes shared working state or publication validates its current owner/fence under transaction lock. A worker resuming after lease expiry cannot publish. Long stages renew heartbeat; a dead owner's lease can be reclaimed after a documented timeout. Model-specific checkpoints advance only when that model's materialization succeeds.

The lease scope covers the shared working target through snapshot/semantic/publish. Per-run state/artifacts use separate directories; never overwrite another run's semantic manifest. Candidate Warehouse snapshots are immutable, so source capture can be decoupled later after measured need.

Acceptance includes two competing publishers and an expired owner, not only serialized happy-path runs.

## Semantic release binding

Planned implementation contract: semantic_input views filter warehouse_store by a required session setting sales_dw.candidate_release_id. The semantic runner validates a UUID, validates release state/source_cut, establishes the setting on every database connection and verifies it before issuing metric queries.

A missing/invalid setting fails closed. No default means no accidental all-release aggregation. PostgreSQL/libpq connection options and dbt/MetricFlow adapter propagation must be verified by V-017; offline SQL compilation does not prove connection initialization.

semantic_input is never granted to the BI role. Warehouse presentation always selects the published release independently of that session setting.

An alternative connection-binding implementation is admissible only with a successor ADR and identical isolation/parity evidence; do not do string replacement of arbitrary generated SQL.

## BI release binding

Expose validated, retained reporting exports with release_id. The delivered dashboard URL includes one explicit release_id parameter applied to every card. Month filters operate within that release. A card cannot silently fall back to another version.

This avoids the browser race in which independent chart requests observe different pointer values during publication. A separately generated latest-dashboard link resolves the pointer once, then opens the pinned URL.

Warehouse publication and the Metabase API are not an atomic distributed transaction. A BI notification/link update failure leaves the valid pinned prior dashboard usable and records delivery lag; it does not invalidate the committed Warehouse release or claim cross-system atomicity.

## Schema and migration management

Versioned migrations own ops, registries, Warehouse store, presentation/semantic views, reporting tables, roles and indexes. dbt owns only its working schemas/materializations. No ad-hoc DDL through diagnostic tools.

Prepare migration plan, target/rollback/backup implications and checksums before applying through the designated migrate entrypoint and applicable human gate. Existing database replacement/destructive reset is never an implicit recovery method.

Schema evolution expands compatible fields first, tests old/new readers, backfills/rebuilds versioned candidates, then retires old contracts by a documented release. Model changes create a new release without overwriting the last validated one.

## Resources and failure domains

Target measured footprint <70 GB, initial goal 20–30 GB including raw, source versions, working models, two retained Warehouse+metric releases, candidate, WAL, backups, logs, image/build caches.

Shared PostgreSQL process resources mean metadata and analytical workloads can contend. Start with separate databases/users and connection quotas; isolate into separate instances only if measurements justify it. No claim of HA or host-loss protection from same-host volumes.

External interfaces bind to loopback. Production outside this machine would require separate availability, backup placement, TLS/access and capacity decisions.

## Primary implementation references

- https://www.postgresql.org/docs/17/libpq-envars.html (PGOPTIONS/options)
- https://www.postgresql.org/docs/17/runtime-config-custom.html (two-part custom settings)
- https://www.postgresql.org/docs/17/btree-gist.html (typed temporal exclusion support)

These support the PostgreSQL mechanism, not proof that a particular dbt/MetricFlow adapter propagates the setting; the adapter-specific runtime gate remains mandatory.

