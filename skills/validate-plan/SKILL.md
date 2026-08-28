---
name: validate-plan
description: Use in Harness4Codex L2 pipelines to validate implementation-plan coverage, order, evidence and reversibility against spec and design.
---

# Validate Plan for Harness4Codex

Audit the plan before implementation:

1. Map every P1 REQ/AC to a concrete task and test.
2. Confirm dependency order, migration/rollback sequence and ownership boundaries.
3. Confirm each task names files, expected red test, implementation action and green
   verification command.
4. Check graph blast radius and design `applies_to` coverage.
5. Label missing coverage, circular dependencies, unsafe irreversible steps and
   unmeasurable success criteria.
6. Permit at most two autonomous plan revisions; unresolved material choices open
   `approve-plan` with exact alternatives and consequences.

Record artifact type `validated-plan`. Approval advances to TDD.
