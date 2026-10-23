# Consumer and workload map

| Consumer | Question | Workload and volume | Access | Freshness | Serving |
|---|---|---|---|---|---|
| Business reviewer | Delivered sales, orders, AOV and customers by month? | OLAP; ~100k orders, one/two concurrent viewers | Monthly cards, daily trend | Explicit retained published release | MetricFlow-generated exports -> PostgreSQL -> Superset |
| Commercial analyst | Category/seller contribution? | OLAP; ~113k item rows, top-N and month/category | Aggregation and breakdown | Same release as overview | Item semantic model and exports |
| Customer/service analyst | Observed repeat/cohort/recency, eligible on-time deliveries, payment records? | OLAP over published order/customer/payment read models; 100k orders | Explicit cohort/cutoff/denominators; no atomic fact joins | Same release as overview | Governed published SQL views -> Superset; SQL Lab and reproducible report/notebook |
| Data engineer | Missing data, drift, recovery, source reconciliation? | Batch operations, small append-only run records | Logs, DQ issues, manifest state | Per task/run | Airflow + operations tables |
| Interviewer | Trace a KPI and reproduce it? | CLI query and bounded SQL inspection | Read-only facts, semantic SQL and evidence | On demand | MetricFlow CLI, SQL, documentation |

Historical depth: snapshot 2016–2018. Batch replays are accelerated operational simulations.
No low-latency application API or event stream is required. PostgreSQL serves the measured workload; no serving database or distributed engine is justified.
Provisional UX target: common published monthly charts return in 5 seconds on the target machine; measure before claiming it.

