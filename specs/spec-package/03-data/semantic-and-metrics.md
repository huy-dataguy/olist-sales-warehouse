# Semantic models, metrics and BI contract

## Capability and version

Semantic models declare entities, dimensions and reusable aggregations. The executable semantic layer discovers valid combinations, generates SQL, executes it at an explicit Warehouse release and provides consistent consumer output.

Local MetricFlow + dbt Core/PostgreSQL is mandatory; paid cloud services and an assumed native Metabase connector are not dependencies. The tested representative configuration uses the dbt 1.12 model-embedded semantic syntax and a day-grain time spine.

Machine contract: contracts/metric-catalog.json (version 2.0.0).

## Kimball semantic graph

- Orders: primary order; foreign customer, buyer_geography and order_status; purchase date and milestone fields.
- Sales lines: primary order_item; foreign customer, product, seller, buyer_geography and order_status; purchase date.
- Payments: primary payment record; foreign customer, buyer_geography, order_status and payment method; purchase date is context only.
- Dimension entities use their warehouse-managed keys.

No semantic foreign-order path links an item fact to the order fact. Metrics drill across independently aggregated facts using common time and buyer_geography dimensions. Item metrics can use product/seller; general order count/AOV cannot fan out to item dimensions.

The offline probe now verifies this conformed-dimension graph rather than the earlier fact-to-fact order-context example.

## Metric dictionary

| Metric | Definition | Allowed dimensions | Additivity |
|---|---|---|---|
| total_orders | count accepted orders | purchase day/month, buyer state | additive |
| delivered_orders | sum delivered order flag | purchase day/month, buyer state | additive |
| canceled_orders | sum canceled order flag, unavailable separate | purchase day/month, buyer state | additive |
| cancellation_rate | canceled_orders / total_orders | shared order dimensions | ratio |
| delivered_merchandise_value | sum item price with accepted delivered status, excluding freight | purchase day/month, buyer state, category, seller | additive |
| delivered_aov | delivered_merchandise_value / delivered_orders | shared order dimensions only | ratio |
| delivered_unique_customers | distinct durable customer with delivered order | requested purchase period, buyer state | non-additive distinct |
| delivered_item_rows | count item rows with delivered status | item dimensions | additive |

Technical common geography dimension: buyer_geography__state.
Category: product__category. Seller: seller__seller_id.
Dates use the same purchase calendar definition and day-grain time spine excluding reserved date members.

All sales metrics use accepted snapshot status and purchase date, not historical knowledge as of purchase. BRL is a demo convention because source rows lack currency. Merchandise value is not net revenue or platform fees.

Zero denominator -> null. Money aggregates exactly to cents; generated ratio comparison tolerates engine representation at 1e-9. Round for presentation only.

Distinct durable customer identity must remain stable across any future customer SCD changes; a version-specific SK would require a separate durable-identity aggregation. Current real customer dimension is Type 0 identity.

## Full real-source baseline

total_orders=99441; delivered_orders=96478; canceled_orders=625; delivered_merchandise_value=13221498.11; delivered_item_rows=110197; delivered_unique_customers=93358.

These were computed from the actual source archive with Python Decimal. Runtime Warehouse/semantic parity remains pending.

## Release-bound execution and BI

See ../02-architecture/production-local.md for immutable Warehouse snapshots, required per-connection semantic release binding and fencing. Missing/wrong binding fails closed. Adapter connection initialization is an implementation spike; compile-only evidence does not certify it.

Exporter executes fixed MetricFlow requests against one explicit release, stores generated SQL/manifest hashes and typed results in five versioned exports: sales_monthly, sales_daily, product_monthly, seller_monthly and buyer_state_monthly.

Superset reads only ever-published reporting views. Each business virtual dataset is pinned to one explicit release literal and assets are versioned by release. Native filters select the month without changing that binding. Monthly distinct reads the direct monthly result and fails closed without a single-month context; state/day distincts cannot be summed. Daily trend exports are additive-only. ADR-014 adds published order/customer/cohort/payment SQL views for extended analysis, separately governed and verified rather than mislabeled as MetricFlow definitions.

Superset asset/link delivery is outside the Warehouse transaction. A failed delivery leaves prior pinned output valid; do not claim a cross-system atomic commit.

## Proof

Current: offline parse, discovery, conformed-geography cross-grain ratio SQL, category SQL and forbidden category grouping rejection. Independent golden data also checks ratios, distincts, no-fanout and role dates.

Required runtime: actual PostgreSQL MetricFlow execution, connection release binding, source/SQL/golden parity, all exports and three dashboards, wrong-release failure, zero denominator and concurrent-publication/browser isolation.

References:
- https://docs.getdbt.com/docs/build/semantic-models
- https://docs.getdbt.com/docs/build/metricflow-commands
- https://github.com/dbt-labs/metricflow

