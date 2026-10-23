# Warehouse model summary

Authoritative dimensional design: [kimball-design.md](kimball-design.md).
Machine contract: contracts/warehouse-model.json.
Physical draft: db/design/001_warehouse_schema.sql, design-only and not executed.

## Business process, grain and dimensions

| Fact | Type | Grain | Conformed dimensions |
|---|---|---|---|
| fct_order_items | Transaction | source_system + order_id + order_item_id | purchase date, customer, product, seller, buyer geography, order status |
| fct_payments | Transaction | source_system + order_id + payment_sequential | purchase date as context, customer, buyer geography, order status, payment method |
| fct_orders | Accumulating snapshot | source_system + order_id | purchase/approved/carrier/delivered/estimated date roles, customer, buyer geography, order status |

Seven dimensions: dim_customer, dim_product, dim_seller, dim_buyer_geography, dim_date, dim_order_status, dim_payment_method.

Warehouse-managed bigint surrogate keys are allocated once in a registry; date keys are YYYYMMDD with sentinel members. Natural IDs remain for lineage. Hashes fingerprint payloads and do not replace the dimension key registry.

order_id is a degenerate dimension. Atomic fact-to-fact joins are prohibited for metric aggregation; aggregate each process independently to shared dimensions.

## dbt model responsibilities

Planned paths:
- dbt/models/staging/stg_olist__{customers,orders,order_items,payments,products,sellers,category_translation}.sql: source-at-cut normalization.
- dbt/models/intermediate/int_order_item_totals.sql and int_order_payment_totals.sql: independent order aggregates.
- dbt/models/intermediate/int_orders_enriched.sql: source order context, customer identity and order-time geography; LEFT-preserved coverage.
- dbt/models/dimensions/: seven registry-keyed dimensions.
- dbt/models/facts/: three working fact models and model checkpoints.
- dbt/models/quality/: source, grain/key, payment and completeness reconciliation.
- dbt/models/semantic_input/: release-bound views over immutable Warehouse snapshots.
- dbt/models/semantic/semantic_models.yml: declarations on the semantic input models.

These are planned implementation paths, not existing models. Working models are not consumer-facing. Frozen consumer copies and presentation views share release identity.

## Historical/source behavior

Olist is a final snapshot. Use Type 0/1 appropriately; do not fabricate Type 2 history. Explicit-effectivity fixtures define reusable Type 2/late-arrival behavior. Order-time buyer geography is resolved from each source customer_id, separately from durable customer_unique_id.

Keep source category/null/missing-child cases visible. Missing recorded payment is unknown, not an observed zero. Delivered status with absent delivery timestamp still counts as delivered but is ineligible for delivery-timing metrics.

## Incremental consistency

Accepted source versions are append-only and read at a fixed source_cut; admission commits are serialized/fenced. A revision conflict cannot silently overwrite current data.

Affected orders include changed parents and children. Recompute all relevant order/line/payment classifications for those orders, including old orders with new status. Each model advances its checkpoint only with successful materialization.

Same-batch delivery creates audit attempts, not new entities or dimension keys. Full rebuild uses the retained registry. Independent fresh-target comparisons normalize SKs back to natural identities unless they restore the same registry first.

## Required physical integrity

Consumer store has release-scoped PK/unique/FK constraints and typed money. Facts reference dimensions from the same release. Unknown/inferred members are explicit; applicable fact keys are not nullable. Draft schema is syntax-checked offline; actual migration/dbt materialization/index/constraint behavior remains a runtime gate.

