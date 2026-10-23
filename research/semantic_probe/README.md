# Offline semantic compatibility probe

This is a representative configuration fixture, not the Olist Warehouse implementation. Models contain tiny illustrative SELECTs and are never materialized by the probe. The dummy PostgreSQL profile intentionally uses port 1.

Pinned environment: dbt-core 1.12.6, dbt-postgres 1.11.0, dbt-metricflow 0.15.0, metricflow 0.213.0; Python 3.12.

Run from repository root:

```bash
uv run --python 3.12 --with dbt-core==1.12.6 --with dbt-postgres==1.11.0 --with dbt-metricflow==0.15.0 python scripts/probe_semantics.py
```

Checks: dbt parse, metric discovery, cross-grain monthly/state ratio SQL through conformed buyer geography, category-level item SQL, expected rejection of order counts grouped by item category. The facts do not use a direct foreign-order semantic path. The last command must return exit 1 with an unsupported-grouping diagnostic for the probe to pass.

The parser requires a day-grain time spine even for this simple configuration; models/time_spine.sql and its YAML configuration provide it. The probe uses the dbt 1.12 model-embedded semantic specification.

Evidence is generated at docs/evidence/semantic-probe.json. SQL generation is offline; actual PostgreSQL execution, zero-denominator result testing, real-data parity and Metabase consumption remain V-005/V-006 implementation gates.
