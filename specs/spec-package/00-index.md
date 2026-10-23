# Project specification

## Status

architecture-baseline — expanded production-local design 2.0.0, 2026-10-15.

Historical baseline: design/specification and independent verification first. On 2026-10-15 the user subsequently authorized implementation and isolated migrations/restores. The architecture/REQ/V contracts below remain the design authority; actual bounded runtime results are tracked in [implementation progress](../../docs/implementation-progress.md) and [runtime evidence](../../docs/evidence/README.md). This is not blanket production acceptance.

## Purpose

An enterprise-engineered local Sales & Customer Analytics Warehouse: Kimball dimensional integration, executable semantics, controlled publication, source/quality correctness, security and recovery.

## Authority

User scope and applicable safety rules > versioned data/metric/release contracts > this package > implementation preference. DSH TEMPLATE_VERSION remains 1.0.0; domain contracts advance to 2.0.0.

## Read first

- [Vietnamese product design](../../docs/PRODUCTION_DESIGN.md)
- [Implementation readiness](../../docs/implementation-readiness.md)
- [Shared contract](00-contract.md)
- [Requirements](01-product/requirements.md)

## Architecture and data

- [Consumer workloads](02-architecture/consumer-workload-map.md)
- [System architecture](02-architecture/system-architecture.md)
- [Production consistency](02-architecture/production-local.md)
- [Security/governance](02-architecture/security-and-governance.md)
- [ADRs](02-architecture/adr/README.md)
- [Source of record](03-data/source-of-record.md)
- [Model summary](03-data/data-model.md)
- [Kimball design and bus matrix](03-data/kimball-design.md)
- [Boundary contracts](03-data/data-contracts.md)
- [Semantic and metrics](03-data/semantic-and-metrics.md)

## Workflow and operations

- [Task graph](04-workflow/task-graph.yaml)
- [Verification matrix](06-verification/verification-matrix.md)
- [Test strategy](06-verification/test-strategy.md)
- [Traceability](06-verification/traceability.md)
- [Implementation plan](07-implementation/implementation-plan.md)
- [Runtime constraints](07-implementation/runtime-constraints.md)
- [Dossier boundary](07-implementation/dossier-admission.md)
- [Operation summary](08-operations/README.md)
- [Operating model](08-operations/operating-model.md)

## Evidence

Real source profiling/contracts, independent synthetic Kimball checks, PostgreSQL DDL grammar/static structure and offline semantic SQL generation are bounded current evidence.

Service-dependent gates must be assessed from executed runtime evidence, not the offline files. See the implementation coverage table for completed checks and remaining limitations; planned commands in older design documents are not proof of execution.

