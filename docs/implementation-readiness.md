# Implementation readiness and open decisions

## Current scope

Historical design handoff, superseded for execution by the implementation authorization on 2026-10-15. A working local Warehouse and UIs now exist. Consult [implementation progress](implementation-progress.md) and [runtime runbook](runtime-runbook.md) for executed evidence and unresolved boundaries; this document preserves the original spike checklist.

## Frozen decisions

- Olist source scope, seven feeds, actual source baseline and separate synthetic fixture.
- Airflow, PostgreSQL, dbt Core, local MetricFlow, MinIO local and Metabase.
- Kimball bus, three business processes, seven conformed dimensions, registry-managed integer SKs and role-playing dates.
- Source cut/version ledger, inferred-member and Type 2 contract, same-release dimension/fact integrity.
- Immutable consumer Warehouse snapshots plus metric exports, fenced publication and release-pinned BI.
- Security roles, backup/restore, CI/release gates, SLO/resource targets and evidence standards.

## Required implementation spikes

These were required runtime checks rather than undecided business scope. Most now have bounded evidence; dependency CVE scanning, remote CI and host-loss recovery remain unverified:
1. Build the pinned MinIO source revision; verify local S3 startup/PUT/GET and freeze image digest.
2. Verify PostgreSQL session release binding survives every dbt/MetricFlow adapter connection. Missing/wrong binding must fail closed.
3. Prove registry stability across incremental and full rebuild, physical dimension/fact integrity and source-cut consistency.
4. Prove lease fencing against a stale owner and two promoters.
5. Configure Metabase mandatory release_id filter/URL binding on every card; test publication while the browser refreshes.
6. Choose exact patch/digest versions for Airflow/PostgreSQL/Metabase, then run dependency/security and resource checks.
7. Execute an isolated backup/restore drill and measure the declared RPO/RTO boundary.

Do not mark these passed from a JSON schema check, offline SQL compile or source profile.

## Migration review boundary

db/design/001_warehouse_schema.sql is design-only DDL. Review its schema/table/key/role implications and turn it into the controlled migration entrypoint before applying. No DDL was executed in the design task.

## Remaining external business information

The actual JD/platform/access model and Abbott product domain are unknown. They affect future connector/dialect/security adaptation, not the integrity of this local Olist reference design. The dataset's noncommercial attribution/share-alike conditions remain separate from the project code license.

## Implementation handoff

Use specs/spec-package/04-workflow/task-graph.yaml in dependency order. After an actual bounded slice has real commands/evidence, populate and admit the executable dossier. Native DSH admission has not been performed in this design-only turn.

