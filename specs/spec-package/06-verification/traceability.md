# Traceability and acceptance

| Requirement | Design/contract owner | Task | Verification |
|---|---|---|---|
| REQ-001 | source-of-record / source contracts | TASK-001 | V-001 |
| REQ-002 | CONTRACT-001 / raw | TASK-002 | V-002 |
| REQ-003 | CONTRACT-002 / admission | TASK-003 | V-003 |
| REQ-004 | Kimball / CONTRACT-003 | TASK-004 | V-004 |
| REQ-005 | semantic-and-metrics / metric-catalog | TASK-005 | V-005 |
| REQ-006 | BI release binding / CONTRACT-005 | TASK-006 | V-006 |
| REQ-007 | quality / CONTRACT-003,006 | TASK-007 | V-007 |
| REQ-008 | architecture / operational scenarios | TASK-008 | V-008 |
| REQ-009 | version/replay / CONTRACT-002,003 | TASK-009 | V-009 |
| REQ-010 | operating model / recovery | TASK-010 | V-010 |
| REQ-011 | workload / benchmark evidence | TASK-011 | V-011 |
| REQ-012 | whole-product runtime handoff | TASK-012 | V-012 |
| REQ-013 | kimball-design / warehouse-model / DDL draft | TASK-013 | V-013 |
| REQ-014 | Kimball effectivity / golden fixture | TASK-014 | V-014 |
| REQ-015 | security-and-governance / role matrix | TASK-015 | V-015 |
| REQ-016 | operating model / backup/restore | TASK-016 | V-016 |
| REQ-017 | production-local / release schema | TASK-017 | V-017 |
| REQ-018 | source-cut architecture / state machines | TASK-018 | V-018 |
| REQ-019 | security-and-governance / CI/change policy | TASK-019 | V-019 |
| REQ-020 | operating model / SLO/resource targets | TASK-020 | V-020 |

Design baseline version: production-local 2.0.0 contracts; DSH template 1.0.0. Current evidence is bounded design/source/offline verification. Full runtime acceptance is pending implementation, explicitly deferred by the user.

Actual handoff records environment locks, artifact/source hashes, registry identity, source/release cuts, commands/exit codes, quality/semantic/BI outputs, security/restore/capacity measurements and failed/skipped gates.

