# Source of record and data policy

## Authoritative records

| Domain/state | Source of record | Derived outputs |
|---|---|---|
| Published business snapshot | Original Olist v2 archive, SHA-256 in source-profile evidence | Landing, dimensions/facts, metrics |
| Raw receipt/replay | Immutable source artifact + explicit manifest | Ingestion batch state |
| Accepted source versions | Append-only observed versions and serialized commit boundary | dbt working models at fixed source_cut |
| Dimension identity | ops.dimension_key_registry, stable warehouse-managed integers | All conformed dimensions/fact SK lookups |
| Consumer Warehouse | Immutable release-scoped typed dimensions/facts | Published analyst views and semantic inputs |
| Metric meaning | Versioned semantic YAML + this metric contract | Generated SQL and export tables |
| BI visibility | ops.published_release | Published reporting views |
| Orchestration status | Airflow metadata, linked with ops pipeline_run_id | Health dashboard |

Publisher: Olist, Brazil. Origin: https://www.kaggle.com/datasets/olistbr/brazilian-ecommerce.
Download: https://www.kaggle.com/api/v1/datasets/download/olistbr/brazilian-ecommerce.
License metadata: CC BY-NC-SA 4.0. Attribute Olist; do not relicense source/derived data under the code license. Confirm intended use before commercial reuse.

Checked artifact: 44,717,580 bytes; SHA-256 967e41e04fc306fe604e2a693f488995a8b41e5047418f8a5c8e4abd6deca784.

## Source semantics

CSV timestamps have no timezone offset. Keep source timestamps as timestamp without time zone and derive purchase calendar dates as published. Do not silently localize them to UTC or infer historical daylight-saving behavior. Real ingested_at timestamps are UTC.

CSV has no currency column; BRL is an explicit demo business convention, not a verified per-row currency field. Monetary operations use Decimal/numeric, not binary floating-point accumulation.

Source behavior: static sampled/anonymized snapshot, no supported cursor, source_updated_at, delete feed or complete order-status history. Network requests are bounded archive downloads, checksum-verified; unavailable/auth-changed downloads produce a recoverable source error, not an empty successful batch.

## Seven v1 feeds

- customers: customer_id is the per-order reference; customer_unique_id identifies the customer across orders.
- orders: one row per order_id.
- items: one row per (order_id, order_item_id); no quantity field. Do not interpret order_item_id as a product ID or multiply price by it.
- payments: one row per (order_id, payment_sequential); installments count is not a multiplier on payment_value.
- products: product IDs, categories and physical/description-length metadata; no actual product names.
- sellers: marketplace sellers, not telesales vendors.
- category translation: mapping; untranslated nonempty categories retain their original code.

The complete inventory/null profile lives in docs/evidence/source-profile.json. Reviews and geolocation remain outside v1 processing even though their files are preserved in raw.

## History, retention and replay

Keep original archive/checksum for the lifetime of the demo. Derived replay slices refer back to its checksum. Keep only necessary derivative formats; no mandatory CSV+Parquet copy of every layer.

Initial reference data is loaded as a declared snapshot. Replay partitions orders by purchase month and carries the associated customer references/items/payments; manifests define ordering and completeness. This is operational replay of final-snapshot records, not historically accurate point-in-time source delivery.

Simulated corrections/late children have separate scenario_id, source_revision and observed_at fields assigned by the simulator. These fields are never claimed to come from Olist. Golden sales and effectivity fixtures use separate scenario identities/targets; neither updates the real-source business baseline.

