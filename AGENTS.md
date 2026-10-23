# Project working agreement

Read README.md, specs/spec-package/00-index.md and specs/spec-package/00-contract.md before implementation.

The design baseline is specs/spec-package/. Follow the dsh-spec-authoring contract at /home/dataguy/.agents/skills/dsh-spec-authoring/references/spec-contract.md when changing requirements. TEMPLATE_VERSION is 1.0.0.

Preserve user decisions: Airflow, dbt at the center, PostgreSQL, executable semantic models/MetricFlow, Olist business data; telesales is outside v1. The user's subsequent decision replaces Metabase with Apache Superset and requests a question-driven dashboard suite plus reproducible business analysis. Keep the scope local demo; do not introduce production expansion, Dagster or claims about internal Abbott/Concentrix architecture.

State current status honestly: design/source research is not a working Warehouse. Do not admit dossier.json until implemented runbooks exist. Requirements and V-* references are stable. Planned paths in specs are future implementation contracts.

Use apply_patch for source/document edits. Do not commit raw archives, credentials or generated database volumes. Do not execute CREATE/DROP/ALTER/TRUNCATE directly through ad-hoc tools: planned provisioning/migrations require the designated controlled entrypoint and the applicable human gate. Read-only research and offline compilation do not require a migration.

Do not invent source_updated_at, source CDC, historical SCD2, customer names or product names. Generated operational fixtures must be marked simulated and isolated from real-source baselines.

Raw sources are immutable; preserve lineage and checksums. Validate grain before joins. Distinct customer counts are not additive. Failed checks must not advance the published release.

No delegation is requested by this project agreement.

Current user choice: complete design/specifications first; implementation later. Design authority now includes docs/PRODUCTION_DESIGN.md, the Kimball bus/registry contract, production-local release isolation, security/governance and operating model. Use warehouse-managed integer dimension SKs, conformed dimensions and drill-across; do not restore the superseded hash-key/fact-to-fact design.

Run make verify-design for design handoff. These checks validate source/contracts/fixtures/DDL syntax/offline semantics, not runtime services. Keep DDL in db/design/ unexecuted during design-only work; actual migrations and service verification require a subsequent implementation task. Do not label the product production-ready from offline design checks.

Implementation authorization (2026-10-15): the user now explicitly requested building the system and approved creating/migrating isolated sales_dw, airflow_meta and metabase_meta databases plus dedicated roles/schemas inside Compose project salesdw. This supersedes the previous design-only pause. Use scripts/migrate.py (plan/apply, checksummed migrations); do not touch unrelated databases/containers. Restore drills require a separately scoped isolated target, never replacing these live databases.

BI revision authorization: build Superset and its isolated project metadata via the controlled migration entrypoint. Add only governed published analytics views to sales_dw; preserve source/fact grains, MetricFlow definitions and existing releases. Retain the prior Metabase database/files as historical artifacts; do not erase them to switch the default UI.

