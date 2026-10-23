# Shared engineering contract

## Scope and authority

This package was authored as complete production-local design/specification, real source data, independent fixtures and executable design checks. The user's subsequent implementation authorization on 2026-10-15 supersedes the earlier pause. No design-only check certifies production readiness; runtime acceptance is evidence-bounded.

User business scope and applicable safety rules govern the versioned contracts/specs. Approved implementation is confined to Compose project salesdw and its dedicated databases/roles. Actual schema application uses scripts/migrate.py plan/apply with checksums; restore only creates separately authorized isolated sales_dw_restore_* targets. No reset/drop or unrelated container/database changes are authorized.

## Ownership

Business steward owns KPI/source meanings. Ingestion owns capture/admission/version metadata. Warehouse owner owns Kimball conformance and registry. dbt owns working transformations. Snapshot/semantic/publisher services own their controlled boundaries. Airflow owns orchestration state. BI owns presentation of published releases.

## Terms

- Source: Olist, one publisher with multiple domain feeds.
- Source snapshot: immutable v2 archive and checksum.
- Replay plan/batch/receipt: deterministic input sequence versus each delivery attempt.
- Source cut: a committed consistent boundary over accepted observed source versions.
- Working state: rebuildable incremental models, inaccessible to business consumers.
- Warehouse release: immutable typed seven dimensions + three facts at one cut.
- Published release: complete validated Warehouse and exports, selected by publication pointer.
- Semantic context: an explicit verified release on every engine connection.
- Pinned dashboard: all cards use the same retained published release ID.
- Effectivity: business valid time only when supplied; capture time is not automatically business valid time.
- Evidence: command/environment/inputs/exit/result artifact, not a claim that a file exists.

## Invariants

- Stable unique REQ-*, TASK-*, V-*, ADR-*; requirements have observable criteria and task/check coverage.
- Planned, failed or skipped verification never counts as system acceptance.
- Source-native raw is immutable; original and synthetic scenarios remain separated.
- Dimension SKs are warehouse-managed stable integers; hashes are payload fingerprints.
- Fact grains and conformed dimensions precede physical design. No atomic fact-to-fact metric joins.
- Every applicable FK resolves within the same release, including explicit unknown/inferred members.
- Preserve source order-time geography and nullable milestones; no invented history/names/IDs/currency evidence.
- Money uses Decimal/numeric. Distinct customers and ratios cannot be naively rolled up.
- All models see the same source cut; all consumer rows/queries share release identity.
- Failed validation, partial exports or stale fences cannot promote. Publish-commit acknowledgement loss is a distinct idempotent recovery case.
- No operator reset replaces diagnosis, restore verification or source reconciliation.
- Contract/architecture changes get an ADR and recorded impact/review; migration application follows the applicable safety boundary.

