# Security, governance and change control

## Data classification

Olist is an anonymized public dataset with pseudonymous identifiers and geographic attributes. Treat raw and linked customer identities as restricted project data; do not call it guaranteed non-personal data. No patient records, real credentials or company-internal information are added.

License: CC BY-NC-SA 4.0 according to publisher metadata. Attribution and restrictions apply to source/derived data separately from project code. The local portfolio is not authorization for commercial customer deployment with this dataset.

## Role and permission matrix

| Role | Allowed | Explicitly excluded |
|---|---|---|
| bootstrap_owner | Controlled schema/role migrations | Daily orchestration credentials |
| ingestion_service | Raw PUT/GET, receipt/version/quarantine admission | Public release pointer, dbt model DDL, arbitrary delete |
| transform_service | Read accepted source at cut; dbt-owned working schema; key resolution via controlled interface | Editing raw source, BI application admin |
| snapshot_service | Read validated work; append immutable Warehouse candidate | Changing prior validated snapshots |
| semantic_service | Read an explicit release through semantic_input; write candidate exports | Source mutation or publication |
| publisher_service | Validate candidate ledger/fence and atomically promote | Altering source/model results to pass checks |
| analyst_readonly | Published Warehouse views | landing/work/private ops |
| bi_readonly | Validated reporting exports and redacted health views | Raw/customer linkage, candidate data, migrations |
| backup_operator | Consistent backup/isolated restore, controlled retention | Routine application/publisher identity |

Actual PostgreSQL roles may share a process but must not silently become one superuser credential. Grant only required schema/table/function/sequence privileges; test denied operations as well as allowed ones.

## Secrets and network

Generate distinct local secrets, store outside git in ignored configuration or Compose secrets, restrict filesystem permissions and never log connection URLs/passwords. Provide .env.example with placeholders only. Redact run evidence and quarantine samples.

Bind UIs to loopback, keep database/object service ports private except an explicit developer profile. MinIO/DB root credentials are initialization/operator secrets, not ingestion/BI credentials.

Local loopback isolation is the baseline trust boundary. Any remote access requires a deployment ADR covering TLS, authentication, access controls and maintenance. Do not present password defaults or unmaintained binaries as enterprise production security.

## Governance and approvals

Version source, normalized, Warehouse and metric contracts. Every breaking field/grain/metric change gets an ADR, compatibility impact, migration/backfill plan, affected consumer list and explicit review record.

Routine authorized reversible work follows the user's scope; do not add repeated approval prompts. Schema application/destructive operations use their designated controlled gate. A retained production-like environment is not wiped to make tests pass.

Keep a data decision log: source warnings accepted by policy, reconciliation thresholds with reasons, unsupported analytical questions, currency/time assumptions, processor versions and release acceptance evidence.

## Audit and lineage

Track artifact/member/source row -> accepted version -> batch/source cut -> dbt model/version -> Warehouse release/SK -> semantic metric/SQL hash -> reporting export -> dashboard/card.

Audit actor/service, timestamps, attempt, previous/new state, reason, source/release identity, fencing token and error category. Store redacted logs and concise lineage keys, not entire customer payloads in Airflow XCom.

Use schema-level source catalog, dbt documentation/manifest/run_results and model/column mapping. A separate paid lineage platform is unnecessary.

## CI and release process

PR gates: formatting/static checks, schema validity, spec/contract references, golden fixture checks, semantic parse/SQL compilation and unit tests of contracts/versioning/state transitions.
Isolated integration gate: actual PostgreSQL/S3, migrations, dbt build, source-to-fact/MetricFlow parity, privilege denial, replay/recovery and publication isolation.
Release gate: pinned lockfiles/images, reviewed migration plan, artifact hashes, traceability, resource/performance/restore evidence and explicit supported-environment statement.

Do not run fixture tests against the persistent local production-like target. CI secrets are scoped and masked. No cloud deployment or external messages are authorized by this design alone.

## Dependency policy

Lock Python and container versions after compatibility testing; capture SBOM/license inventory and vulnerability scan results. Pin MinIO source revision and resulting image digest; record its maintenance limitations. A scan finding needs a documented treatment decision, not an invented universal pass threshold.

Update dependencies in bounded changes with regression and restore tests. Preserve prior working locks/images required for recovery.

