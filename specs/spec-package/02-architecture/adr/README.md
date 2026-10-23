# Architecture decision records

Baseline decisions follow the user's explicit scope, not any company's internal implementation.

| ID | Decision | Reason / consequence |
|---|---|---|
| ADR-001 | Olist commerce, seven feeds; telesales/NHS/Marketing Funnel excluded | Related real data supports bounded sales/customer/product outcomes; one publisher acknowledged |
| ADR-002 | PostgreSQL Kimball Warehouse, Python and dbt Core | Local OLAP workload; no distributed engine/lakehouse required |
| ADR-003 | Airflow LocalExecutor with isolated dbt environment | User choice and bounded scheduling; avoid dependency conflicts and unnecessary queue |
| ADR-004 | Local semantic models/MetricFlow mandatory; Metabase consumes governed exports | Executable metric logic without paid cloud/native connector assumption |
| ADR-005 | Accepted version/source-cut replay; no invented source CDC/history | Static published snapshot requires honest incremental simulation |
| ADR-006 | Pinned MinIO source build only within local reference trust boundary | Community upstream unmaintained/source-only; build/S3/image/maintenance gate and swappable S3 adapter |
| ADR-007 | Whole consumer Warehouse snapshot plus metric exports and atomic pointer | Supersedes export-only protection; analysts and BI need same-release dimensions/facts/results |
| ADR-008 | Per-metric dimension allowlist and monthly pinned exports | Protect ratios/distincts/grain; no product-level AOV without contract |
| ADR-009 | Controlled schema provisioning and isolated recovery | No ad-hoc DDL or destructive reset as diagnosis |
| ADR-010 | Warehouse-managed integer SKs, Kimball bus and conformed geography | Supersedes baseline hash-dimension keys and fact-to-fact order-context semantic path |
| ADR-011 | Explicit Type 2/inferred/late-arrival contract with isolated known-effectivity fixtures | Demonstrate correct capability while preserving real snapshot provenance |
| ADR-012 | Least privilege, consistent backup/restore, CI/change control and measured SLOs | Local operation still needs enterprise integrity/recovery controls |
| ADR-013 | Design/specs first, implementation later | Explicit user answer in this turn; runtime gates remain pending |
| ADR-014 | Superset reporting plus question-driven analysis replaces Metabase for the local demo | Explicit subsequent user choice; retain governed MetricFlow KPIs, add published order/payment analytical views, cohort/cutoff semantics, isolated Superset metadata and real browser evidence |
| ADR-015 | Executive entry plus five specialist dashboards, with release/month-preserving navigation | User requests a large business overview with paths to detailed reports; avoid a single overloaded page, preserve fixed-window customer/trust semantics and existing Warehouse grains |
| ADR-016 | Business-first presentation; remove repeated documentation panels | User rejects verbose shared introduction/reading/limitations blocks. Show compact context, navigation, KPIs and findings; retain methodology in descriptions/docs and technical provenance on the trust page |

## Context, alternatives and consequences

ADR-001: Bank Marketing lacks call grain/IDs; retail-only alternatives have fewer connected entities. Olist seller is not a telesales vendor and products are not renamed into healthcare brands.

ADR-004/008/010: SQL marts alone do not prove semantic execution. MetricFlow aggregates each fact independently over conformed dimensions. Dashboard cards are bound to a release, avoiding pointer races and non-additive rollup errors.

ADR-005/011: Use Type 0/1 for the real snapshot. Version/effectivity history is accepted only with explicit provenance; fixture business time is not represented as observed Olist history.

ADR-006: Source revision 7aac2a2c5b7c882e68c1ce017d8256be2feea27f was checked through upstream GitHub API. A guessed legacy image lookup failed. Foundation must verify build dependencies, S3 behavior and artifact digest; resolve a successor ADR if unavailable or the deployment boundary changes. No paid AIStor account is assumed.

ADR-007: Bounded storage copies are acceptable at ~100k orders. Freeze typed Warehouse/store relations before semantics, then publish all complete artifacts with one fenced transaction. BI API/link delivery is a separate recoverable operation, not cross-system atomicity.

ADR-014 presentation refinement: each report includes decision purpose, query-backed findings, next investigation, reading guidance and limits. Monthly commentary is filtered together with the measured month; customer/trust commentary declares its fixed cutoff/producer. Narrative SQL is versioned as release-bound virtual datasets, not a new Warehouse migration or a new core metric. No causal, profit, churn or SLA verdict is inferred without supporting data/targets. Physical narrative columns use ASCII identifiers and Vietnamese display labels to avoid raw-column alias parsing in the Superset frontend.

ADR-015: executive overview reuses existing MetricFlow exports and published analytical views; independent SQL checks its findings and KPI values. A query-backed navigation strip carries month and release between all six pages. Customer/trust selectors filter navigation only, not their fixed business scope. No new service, Warehouse migration, aggregate star or source data is introduced. Metadata writes use the existing idempotent Superset bootstrap. Current release context is retained rather than silently selecting a different publication during a UI-only change. See docs/analytics-design.md for observable acceptance and scope.

ADR-016 supersedes the requirement to render full purpose/reading/limitations paragraphs on each page. Business context and essential denominator/cutoff notes stay concise and visible. Full guides and release lineage remain in chart descriptions, documentation and the data-trust page. Navigation version 2 renders buttons without duplicate column labels/descriptions. Narrative version 3 shortens follow-up wording and removes technical directions from business findings; its numeric expressions, published business rows and semantic definitions are unchanged. Older virtual definitions remain retained. Browser checks require absent boilerplate, visible findings, overview KPI cards within the first viewport, and retained month/release navigation.

ADR-009/012: Bootstrap/role/schema application goes through reviewed migration and applicable human gate. Backup includes source/version ledger, registry and release state; restore uses an isolated target and invalidates prior leases. Same-host backup is not host-loss HA.

## Evidence and references

- [Kimball bus architecture](https://www.kimballgroup.com/data-warehouse-business-intelligence-resources/kimball-techniques/kimball-data-warehouse-bus-architecture/)
- [MetricFlow](https://github.com/dbt-labs/metricflow)
- [Local MetricFlow commands](https://docs.getdbt.com/docs/build/metricflow-commands)
- [MinIO maintenance notice](https://github.com/minio/minio)
- [PostgreSQL custom settings](https://www.postgresql.org/docs/17/runtime-config-custom.html)
- [PostgreSQL btree_gist](https://www.postgresql.org/docs/17/btree-gist.html)

Changes to grain, keys, metric meanings, security boundary or irreversible migration require a versioned successor decision and consumer/migration impact review.

