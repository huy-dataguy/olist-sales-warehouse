# Golden Kimball fixture

This is deliberately synthetic data, not sampled Olist business history. Source namespace: synthetic_contract_fixture. Keep it isolated from the real-source baseline.

Seven orders cover two months. Manually authored expected.json declares 5 delivered orders, 500.00 delivered merchandise value, 2 distinct delivered customers and 100.00 overall AOV.

Order o1 has two items and two payments: its correct 150.00 item value becomes 300.00 if atomic facts are joined before aggregation. Its correct payment total is 165.00; installments are not a multiplier.

Customer A appears under multiple source customer IDs and both SP/RJ addresses. January has one distinct delivered customer across multiple days. State distinct counts sum to 3 while the overall distinct count is 2. Daily AOV average also differs from the overall AOV.

One delivered order has no delivery timestamp; a delivery later on its estimated calendar day is on time. One payment differs from merchandise + freight by 0.03.

SCD2 changes arrive out of effective-date order. This is a separate scenario (scd2-effective-history-v1), not an update applied to the base sales fixture. A repeated same-payload change must not create an extra version. Exact interval boundaries and inferred-member key stability have separate expected outcomes. Future integration tests must run these scenarios in isolated namespaces/targets.

These values validate design semantics; they are not an implementation or database integration test.

