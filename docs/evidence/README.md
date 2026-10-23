# Evidence scope

Evidence is separated into original offline design research and subsequent real service execution on 2026-10-15. Never substitute one for the other.

## Runtime

UI hiện hành: [Superset manifest](superset/manifest.json), [ảnh tổng quan/sáu trang và hai viewport](superset/screenshots/), [báo cáo phân tích](../../output/analysis/business-analysis.md), notebook/CSV cùng thư mục. `make package-evidence` đóng gói bộ Superset; chart API, SQL Lab, browser render, native filters, actual navigation và metadata replay có evidence riêng. Extended analytics có kiểm grain/cohort/payment độc lập. Navigation revision ngày 2026-10-16 không kế thừa concurrent-publication proof cho các chart mới.

[Historical runtime manifest](runtime/manifest.json) identifies the first Warehouse handoff release, dbt results and five MetricFlow CSVs. Its [screenshots](runtime/screenshots/) were captured from the previous Metabase implementation. This historical bundle is retained; its passing checks do not stand in for new Superset verification. Secrets/raw/backups/volumes are excluded from either bundle.

Detailed machine-local runs/logs live under ignored `var/runs/` and `var/evidence/`. Reports name the isolated targets used for fixtures/restore. A restored database used for later synthetic tests is no longer an untouched restore image. [Runtime coverage and limitations](../implementation-progress.md) distinguish exact outcomes from broader unverified acceptance criteria.

## Original design evidence

- source-profile.json: real source archive downloaded, checksummed and fully scanned. Source values are computed independently using Python Decimal; no Warehouse was used.
- semantic-probe.json: actual local dbt/MetricFlow parse, discovery, PostgreSQL SQL generation and an expected unsupported-dimension rejection. No database connection or DDL.
- design-validation.json: package file/link/identifier/task-graph checks and local source archive identity. This is not native DSH admission.
- design-contracts.json: exhaustive wire validation of 451535 rows from seven real source feeds; independent synthetic Kimball/ratio/effectivity checks; PostgreSQL DDL grammar and AST-level key/grain/FK checks. This is design validation, not executed database constraints.
- ../visuals/visual-verification.json: nine design diagrams exported to SVG/4K PNG/PDF, with label-bounds and local presentation checks. Visual/document quality is not a new runtime acceptance claim.

The environment is pinned through pyproject.toml + uv.lock. `make verify-design` remains an independent offline gate; runtime checks use Docker services. MinIO source build/startup/S3 round-trip have now been exercised, but its unmaintained upstream remains a stated local-profile limitation.
