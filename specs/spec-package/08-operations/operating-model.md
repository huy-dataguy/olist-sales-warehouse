# Operating model, service objectives and runbooks

## Owners and support boundary

One local owner performs the business/data steward, platform operator and release approver roles, but their responsibilities remain distinct:
- Data steward: source/metric contracts, warning acceptance and business reconciliation.
- Platform operator: credentials, services, capacity, backup/restore and incident response.
- Pipeline owner: batches, retries, model/schema compatibility and lineage.
- Consumer/reviewer: validated Warehouse/metric output only.

Maintain an owner field in contracts/requirements; a small team can map people to these roles later.

## Service objectives — targets until measured

| Objective | Target | Measurement and boundary |
|---|---|---|
| Correctness | Exact source/fact money to cents; exact key/count coverage | Same artifact set and declared statuses; known source discrepancies reported |
| Operational freshness | Valid bounded batch published within 10 minutes after acceptance on the measured host | Actual received/published UTC, not 2018 event age |
| Published query latency | p95 <=5 seconds for declared dashboards, 1–2 viewers | Fixed monthly queries, warm/cold conditions recorded |
| Recovery point | <=24 hours of accepted operational state under logical failure | Nightly verified backup plus preserved raw; external copy needed for host-loss protection |
| Recovery time | <=30 minutes on the same healthy host | Timed clean restore into isolated databases, health/KPI/role checks |
| Disk | <70 GB total footprint; initial goal 20–30 GB | Volumes + WAL + raw + exports + backups + image/build caches + logs |
| Availability | Successful health during explicitly declared demo/operation windows | No 24/7 or HA promise for a powered-off/single-host machine |

Missing data freshness, failed task state, publication lag, rising quarantine count, lease expiry and disk thresholds must be independently observable.

## Alerts and severity

- P1: corrupt/incorrect published release or failed restore integrity. Freeze promotion, retain evidence, select last validated release if safe, investigate source/model/version.
- P2: pipeline failure, stale publication, credential/storage/database unavailable, disk >80% of project budget. Keep prior published release; diagnose before retry.
- P3: documented source warnings, late correction admitted, candidate retention pending. Report with owner and evidence.

Notifications are local logs/health views by default. Email/Slack requires explicit destination configuration and authorization; no external message is sent by this design.

## Runbook contracts

| Runbook | Entry command planned | Preconditions | Success evidence |
|---|---|---|---|
| Startup | make up / make verify-boot | Reviewed secrets/config, controlled migration complete | Actual health, DB roles, object read/write, no exposed private ports |
| Initial load | make load-source | Licensed source and matching manifest | Counts, raw hash, source cut, contract/DQ outcomes |
| Next batch | make replay-next | Previous manifest dependencies resolved | New cut and correct incremental results |
| Replay/resume | make replay-batch / make resume-run | Explicit batch/run and source cut | No business duplicates, monotonic states, valid release |
| Correction | make apply-correction | Declared simulated namespace or approved real revision | Changed-order set, revised output, source-version audit |
| Rollback | make rollback RELEASE_ID=... | Retained validated release exists | Pointer change, pinned SQL/BI output and audit |
| Backup | make backup | Operator role and adequate free space | Checksummed dump/manifest, encryption configuration, source and image/contract references |
| Restore drill | make verify-restore | Isolated fresh restore target | Timed restore, counts/KPI/constraints, roles and current release; no change to live DB |
| Credential rotation | make rotate-credentials | New secret prepared, operator access retained | Old credential denied, new connection/retry succeeds |
| Retention | make retention-plan / make retention-apply | Dry-run plan; referenced releases/backups protected | Bounded deletions, retained source/pointer integrity, disk report |

Commands remain planned until implemented; do not put them in an admitted dossier before they exist.

## Backup contents and consistency

Back up PostgreSQL source-version ledger, ops states, dimension key registry, Warehouse/reporting releases and current publication pointer under one consistent database snapshot. Include Airflow/Metabase application databases separately with versions/timestamps. Record that these application backups are not a single cross-database transaction; recreate DAGs/dashboard definitions from versioned artifacts where necessary.

Manifest includes dump checksum, database/server/tool versions, source artifact hashes, schema migration version, dependency/image locks, encrypted secret-reference requirements and restore order. Never write plaintext secrets into evidence or a public repository.

Raw artifacts remain immutable; copy them or verify their preserved external location/checksums. Same-host backup protects logical errors only. Off-host encrypted replication is an optional deployment profile until configured and tested; no host-loss RPO claim without it.

## Restore acceptance

Restore to isolated target; do not DROP/TRUNCATE the active environment as a test. Recreate required roles using controlled provisioning, restore data/schema, invalidate restored leases and mark nonterminal old runs abandoned before enabling workers. Resume accepted batches under a fresh owner/run context, never an old captured lease owner. Validate registry stability and release pointer, run dbt/MetricFlow parity, query BI backing exports, and measure elapsed time. Record failed checks honestly and keep the original service intact.

## Capacity and retention

Warn at 80% of project disk budget; stop optional backfills/candidate generation at 90%, preserve current release/source and diagnose. Bound PostgreSQL WAL with backup/checkpoint strategy; monitor long transactions and autovacuum. Set statement/lock/connection limits per service.

Retain at least the current published release, previous validated release, current candidate diagnostics and the most recent verified backup. Protect any referenced artifact/release. Keep source archive for the project lifetime; apply log/artifact retention only after a dry-run inventory. No broad Docker/system prune.

## Failure injection acceptance

Test failure after raw preservation, after load commit, during dbt, after Warehouse snapshot, during export, before publish and after publish acknowledgement. Test lease expiry/concurrent publisher, network/object store loss, disk-budget admission, schema drift and credential denial.

Expected outcomes: no invalid release visibility, no duplicate business keys, complete attempt/audit trail, deterministic recovery, and accurate Airflow failure. Notifications cannot hide failed upstream tasks.

