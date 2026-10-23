# Kimball dimensional design

## Design method and scope

Apply business process -> grain -> dimensions -> facts in that order. The bus matrix is the integration blueprint, not a collection of unrelated star schemas.

References:
- https://www.kimballgroup.com/data-warehouse-business-intelligence-resources/kimball-techniques/dimensional-modeling-techniques/four-4-step-design-process/
- https://www.kimballgroup.com/data-warehouse-business-intelligence-resources/kimball-techniques/kimball-data-warehouse-bus-architecture/
- https://www.kimballgroup.com/data-warehouse-business-intelligence-resources/kimball-techniques/dimensional-modeling-techniques/accumulating-snapshot-fact-table/

This document supersedes the earlier hash-dimension-key proposal and any fact-to-fact reporting path. Existing fact model names remain stable: fct_orders is the order-fulfillment accumulating snapshot.

## Enterprise bus matrix

| Business process / fact | Purchase date | Other milestone dates | Customer | Product | Seller | Buyer geography | Order status | Payment method | Degenerate order_id |
|---|---|---|---|---|---|---|---|---|---|
| Sales lines / fct_order_items | X | — | X | X | X | X | X | — | X |
| Payment records / fct_payments | X (context only) | — | X | — | — | X | X | X | X |
| Order fulfillment / fct_orders | X | approved, carrier, delivered, estimated | X | — | — | X | X | — | X |

A date on a payment fact is purchase-date context because the source has no payment event timestamp. Product and seller cannot be assigned to an order-level payment without an allocation contract. No invented allocation or many-to-many bridge is introduced.

All conformed dimensions share the same key registry, attribute definitions and unknown-member policy. Reconcile facts by aggregating each separately to their common dimensions, then drill across; never join atomic fact rows to compute business totals.

## Dimension key management

Use ops.dimension_key_registry(namespace, natural_key, version_identity, surrogate_key bigint). The positive surrogate key is allocated once by a sequence/identity, under a unique constraint on namespace + natural key + version identity. It remains stable across batch replay and dbt full rebuild.

Natural keys always retain source namespace. Type 0/1 dimensions use a single durable version identity. Type 2 dimensions allocate a new key per actual effective version. Hashes may fingerprint payloads, but are not the dimension primary key.

Reserved members:
- 0 = Unknown / not yet resolved.
- -1 = Not applicable, only for genuinely inapplicable dimension roles.
- Invalid mandatory source identity = quarantine plus blocked batch by default, not an invented member.

A late-arriving known natural key may get an inferred dimension member with a positive registry key and is_inferred=true. Arrival of descriptive attributes fills that member with the same key. A historical Type 2 correction requires an explicit restatement rule; it is not a silent overwrite.

Every dimension snapshot includes its 0/-1 reserved members before loading fact references. Source-to-dimension reconciliation explicitly separates them and applies the declared dimension grain: 99441 customer references become 96096 durable real customers plus reserved members, while the real static product dimension has 32951 known products plus reserved members. Type 2 scenario version counts are reconciled separately from distinct product identities.

Fact FKs are bigint and required when the dimension applies. Date keys use the conventional YYYYMMDD integer with reserved 0/-1; business timestamp columns retain the actual precision.

## Dimension specifications

| Dimension | Grain and identity | Attributes | Change policy |
|---|---|---|---|
| dim_customer | One durable source customer_unique_id | source_system, customer_unique_id, is_inferred, audit lineage | Type 0 identity; no invented name/gender/segment |
| dim_product | One product version, identified by source product_id plus declared version | source/translated category, physical/source metadata, category_missing flag | Type 1 for the real static snapshot; Type 2 capability tested on explicit revision fixtures |
| dim_seller | One source seller_id / declared version | city, state, postal prefix, is_inferred | Type 1 snapshot; no invented telesales vendor meaning |
| dim_buyer_geography | One exact source address description tuple | postal prefix as text, city, state | Type 0 immutable description; a changed address is a different member |
| dim_date | One calendar date | day, month, quarter, year, weekday, month_start | Type 0; role playing |
| dim_order_status | One source status code | status_code, delivered/canceled flags, description | Type 0 controlled mapping |
| dim_payment_method | One payment type | type_code, description | Type 0 controlled mapping |

Every dimension has its SK, source identity, attribute_hash excluding technical timestamps, created_run_id, last_changed_run_id, source_cut and semantic description. Type 2 members additionally have valid_from, valid_to (exclusive), is_current and business_effectivity provenance.

Product categories are dimension attributes; a separate snowflaked category dimension is unnecessary for this workload. The stable product key remains present when category is missing; its attribute reads Unknown. A known untranslated category keeps its original code.

## Fact specifications

### fct_order_items — transaction fact

Grain: one (source_system, order_id, order_item_id). order_item_id is a line ordinal; there is no source quantity field.

Dimensions: purchase_date_key, customer_key, product_key, seller_key, buyer_geography_key, order_status_key.
Degenerate attributes: source order_id, source order_item_id.
Measures:
- merchandise_value = source price, numeric(18,2).
- freight_value = source freight_value, numeric(18,2).
- item_row_count = 1.
- delivered_merchandise_value / delivered_item_rows are semantic aggregations under the accepted parent status.

Retain original amounts. Never multiply price by line ordinal or installments. Late order-status/correction changes cause affected line classification to be restated under the explicit source-cut policy.

### fct_payments — transaction fact

Grain: one (source_system, order_id, payment_sequential).
Dimensions: purchase_date_key (order context), customer_key, buyer_geography_key, order_status_key, payment_method_key.
Degenerate attributes: source order_id, payment_sequential.
Measure: recorded_payment_value numeric(18,2); payment_record_count=1.
Descriptive numeric: payment_installments (non-additive).
No payment timestamp, recognized revenue, refund ledger or payment-to-product/seller allocation is inferred.

### fct_orders — accumulating snapshot

Grain: one (source_system, order_id), covering every accepted source order even when children are absent.
Dimensions: customer_key, buyer_geography_key, order_status_key, purchase_date_key, approved_date_key, carrier_date_key, delivered_date_key, estimated_delivery_date_key.

Milestone timestamps come from source. Missing milestone date uses key 0 and null timestamp. No periodic backlog snapshot or complete status transition log can be reconstructed from the final Olist snapshot.

Measures: order_count=1, delivered_order_count, canceled_order_count, known_delivery_date_count, on_time_delivery_count, item_merchandise_total, item_freight_total, recorded_payment_total, item_row_count, payment_record_count.
Flags: has_items, has_payments, missing_delivery_timestamp, temporal_anomaly.
Lags: purchase_to_delivery_seconds only if actual dates exist and interval is valid.

Aggregate items and payments independently by order_id, then LEFT JOIN those aggregates to source orders. Distinguish missing child totals from actual recorded zero by presence flags.

Do not sum fct_orders child totals after joining to atomic line/payment facts. They support order-level reconciliation and overview, not additional additive amounts across fact joins.

## Role-playing dates and geography

Each milestone FK references the same dim_date. Sales KPI grouping uses purchase date. On-time delivery compares calendar delivery date <= estimated calendar date; a delivery later on the estimated day is on time.

The 8 source delivered orders without delivery timestamp still contribute to delivered_orders/GMV but not to delivery-time eligibility.

source customer_id is the order's customer/address reference; customer_unique_id is the durable person identity. Resolve customer_key and buyer_geography_key separately. A customer moving SP -> RJ does not rewrite historical SP orders.

Source timestamps are naive; preserve as published. Ingestion/release/audit clocks are UTC. No unverified timezone conversion is permitted.

## Measure additivity

| Measure | Additive across | Do not do |
|---|---|---|
| merchandise/freight/item rows | Disjoint item sets, categories, sellers, purchase dates | Join to multiple payments before summing |
| order count | Disjoint orders, purchase dates and assigned geography | Sum category-level order appearances as total orders |
| recorded payment value | Payment records, methods, purchase context | Multiply by installments or call it platform revenue |
| AOV/cancellation rate | Recompute from aggregate numerator and denominator | Average daily ratios |
| distinct customers | Direct requested grain computation | Sum daily/state distincts |
| milestone lag / installments | Appropriate averages/distributions | Treat as additive totals |
| accumulating order snapshot measures | Current accepted order rows | Sum repeated snapshots of the same order across observation times |

A periodic snapshot is not added merely to demonstrate a pattern; it requires observed daily source states or explicitly simulated history.

## SCD2, early facts and late corrections

Real Olist provides only one published snapshot. Do not fabricate prior product/seller versions. A reusable Type 2 contract is verified with synthetic_contract_fixture:
- effective timestamps are explicitly provided.
- valid intervals are [valid_from, valid_to).
- one current version per natural key; no overlaps.
- same-business-payload repeat creates no new version.
- late effective change can split a historical interval and restate affected fact SKs under a new release.
- as-of lookup at an exact boundary returns the new version.
- an event before known history yields Unknown/diagnostic, not the latest version.
- inferred member enrichment preserves its allocated SK.

Production application to a new upstream system requires trustworthy effectivity or a documented observed-history interpretation.

## Physical and verification contracts

Machine-readable specifications: contracts/warehouse-model.json and contracts/metric-catalog.json.

Staging/working physical layout is not the consumer contract. Stable consumer views expose immutable validated Warehouse releases with all conforming dimensions and facts at one release_id. Foreign-key checks are mandatory dbt/runtime gates; physical PK/unique constraints/indexes are enforced where compatible with the controlled materialization strategy. Ops/registry/release integrity is enforced transactionally in PostgreSQL.

The design-only PostgreSQL draft includes release-scoped PK/FKs, one-current-product-version uniqueness and a btree_gist exclusion constraint for explicitly known Type 2 validity intervals. Snapshot-unknown effectivity is flagged separately and is not presented as historical validity. Extension installation, actual exclusion behavior and migration privileges require isolated runtime verification.

Do not generate fact-to-fact foreign-key relationships in the Kimball ERD.

Required checks: grain uniqueness, not-null applicable keys, dimension referential integrity including reserved members, registry stability, role dates, no orphaning/row loss, no fanout, snapshot/source-cut consistency, SCD validity and source-to-fact reconciliation.

