# Boundary contracts

## Contract catalog and authority

Machine-readable: contracts/source-catalog.json, contracts/source/*.schema.json, contracts/source-batch.schema.json, contracts/warehouse-model.json, contracts/metric-catalog.json, contracts/release.schema.json.

Source wire contracts preserve original CSV string values and nullable empty strings. Normalized typing is a distinct stage. Required columns, identity, timestamp semantics and additional-field policy are explicit; all 451535 selected source rows are checked by the design verifier.

## CONTRACT-001 - Source to raw/ingestion

Producer: Olist v2 publisher or labeled isolated scenario. Consumer/owner: ingestion service.
Identity: artifact SHA-256 plus explicit source/version; member and source row retained.
Batch identity includes replay_plan_id, deterministic selection/revision and sequence. Full-source and monthly replay plans cannot collide merely because they use sequence 1.
Unknown/missing required headers fail the batch after raw capture. Blank key, invalid date/number and equal-revision conflict are quarantined and block admission by default.
Additional columns are not silently discarded. Compatible evolution gets a versioned review.

## CONTRACT-002 - Admission to source versions

Producer: validated source occurrences. Consumer: append-only landing/source_versions.
Metadata: source namespace/declared revision provenance, payload hash, artifact/member/row, batch/receipt, actual received UTC, accepted source commit.
Replay same hash/revision is a business no-op; lower declared revision cannot become current; conflicting equal revision fails.
Commit sequence allocation is serialized with admission so source_cut cannot include a still-uncommitted lower transaction. Do not assume sequence values alone encode commit order.
received = accepted occurrence + duplicate occurrence + rejected occurrence; distinct accepted current entities and version count are separate measures.
Real Olist provides no updated_at/delete feed or revision history beyond its published snapshot. Operational corrections are explicitly simulated, in isolated namespaces/targets.

## CONTRACT-003 - Fixed source cut to Kimball work

Producer: accepted versions resolved at source_cut. Consumer: dbt.
Schemas/grains/keys: warehouse-model.json and kimball-design.md. Registry-backed bigint dimension keys, reserved/inferred members, exact decimal amounts and role dates are mandatory.
Every model records its successful source cut/checkpoint. Parent/child corrections identify all affected orders. Null category/children/milestones are preserved with flags, not fabricated.
Known source warnings are distinguished from transformation defects; bad keys/grain/FKs or dropped valid records block progression.

## CONTRACT-004 - Work to immutable Warehouse release

Producer: validated work. Consumer: warehouse_store.
A consistent snapshot copies all seven dimensions and three facts into typed release-scoped relations. Same-release PK/FK integrity, counts/keysets/checksums, source cut, model/contract versions and lineage are verified before state snapshotted.
Previous consumer releases are immutable until governed retention; no overwrite as a shortcut. Consumers lack work/candidate write access.
Schema migrations provision store/views/ops; normal snapshot/publication is controlled DML.

## CONTRACT-005 - Warehouse to semantic exports and BI

Producer: one immutable Warehouse release. Consumer: MetricFlow, exporter and BI.
Metric definitions, allowed dimensions, time/units/zero/null rules: metric-catalog.json.
Every MetricFlow connection must bind and verify its intended release. Generated SQL/manifest/request identities are recorded. Never replace SQL text to alter model relations opportunistically.
Exports have typed fields, fixed grains and release-scoped identity. All required exports and independent parity pass before promotion.
BI reads ever-published retained releases; every card shares an explicit release parameter. Non-additive distincts/ratios are calculated at requested grain.

## CONTRACT-006 - Operations, lineage and recovery

Producer: all stages. Consumer: ops/health/evidence.
Link source occurrence/version -> batch/source_cut -> model/key -> Warehouse release -> semantic query -> export/dashboard. Store service actor, lease fence, attempt, state transition, counts/timestamps and redacted error reasons.
Fencing/required-check/state transitions define publication. Stale workers cannot commit shared/published state.
Backups include registry/source version states/releases/pointer consistently; restore tests use isolated targets. Recovery never truncates the active environment to hide an error.

## Evolution

Source schema version 1.0.0 describes Olist v2 wire format. Warehouse/metric/release contracts are 2.0.0 for Kimball conformed keys and full-release publication. DSH TEMPLATE_VERSION remains 1.0.0 because its package/identifier authority is unchanged.

