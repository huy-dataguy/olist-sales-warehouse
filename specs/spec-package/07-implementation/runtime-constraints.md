# Runtime constraints

Current work is design-only. The constraints below govern future local deployment.

## Host and supported environment

Inspected Linux host: approximately 22 GiB RAM and 97–98 GiB free disk at research time. Project footprint must remain <70 GB. Actual host state can change; preflight it before startup/backfill.

Initial resource goal: 8–12 GiB RAM and 20–30 GB total project disk, including volumes, WAL, raw, accepted versions, work, retained immutable releases, backup, logs, images and build cache. No full-system capacity measurement exists yet.

Local target: Docker Compose, Airflow LocalExecutor, PostgreSQL 17, Metabase OSS and MinIO source build. No multi-host HA or 24/7 availability claim.

## Locked design-check environment

pyproject.toml + uv.lock pin the design/offline semantic environment. Python 3.12; tested dbt-core 1.12.6, dbt-postgres 1.11.0, dbt-metricflow 0.15.0, metricflow 0.213.0. PostgreSQL grammar parse uses pglast, not a database connection.

Future runtime locks must also freeze container patches/digests, Airflow/provider compatibility, source-built MinIO artifact and any database extensions. Keep dbt dependencies out of Airflow's interpreter.

## Database dependencies

Draft consumer schema uses btree_gist for explicit Type 2 non-overlap plus release-scoped PK/FKs/uniqueness. Installation privileges and actual behavior must be verified through controlled migrations on an isolated PostgreSQL target.

Semantic connection binding uses a required custom setting sales_dw.candidate_release_id. PostgreSQL supports custom two-part settings and libpq options, but dbt/MetricFlow per-connection propagation remains V-017 runtime acceptance.

Source timestamp timezone is unspecified. Do not turn naive dates into assumed UTC business history. Operational clocks are UTC; BRL is explicitly a demo convention.

## MinIO

Upstream community repository is unmaintained/source-only. Selected local revision: 7aac2a2c5b7c882e68c1ce017d8256be2feea27f. A guessed legacy image had no manifest. Source compilation, image digest and actual S3 PUT/GET are pending foundation gates. The S3 adapter boundary permits a reviewed future substitution if that artifact fails or the deployment trust boundary changes.

## Security and resilience

Use distinct scoped service credentials, ignored/restricted secrets and loopback UIs; keep private storage/database paths internal. The research profile's dummy credentials/port 1 are offline-only.

Preserved raw allows reprocessing without source network. A missing storage/DB/semantic dependency fails the relevant stage and never fabricates empty success. Published immutable output remains valid until replaced/retained under policy.

## Operational bounds

Use the operating-model SLO/RPO/RTO/retention targets as goals until measured. Same-host backup protects logical failure only. Restore uses a fresh isolated target and invalidates old leases/inflight owners. No broad system pruning or unreviewed DROP/TRUNCATE recovery.

Record cold/warm query conditions and data/registry identity when comparing performance/rebuilds.

