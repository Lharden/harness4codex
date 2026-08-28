---
name: design-doc
description: Use after an approved Harness4Codex L2 spec to define architecture, data, API, test and rollout mechanics with traceability.
---

# Design Doc for Harness4Codex

Create `docs/specs/{slug}-design.md` from the bundled template.

- Link every design decision to REQ/AC identifiers.
- Declare `applies_to` globs so changed code can discover its governing design.
- Describe components, data model, API/CLI contracts, invariants, concurrency,
  degraded operation, migration, rollout and rollback.
- Include test strategy from unit through conformance, and measurable observability.
- Cite graph paths and source files used as evidence.
- Surface undecided tradeoffs at the human gate instead of silently choosing them.
- Record artifact type `design` and transition to `validate-plan`.

The design explains how the approved spec will be realized; it cannot silently rewrite
the behavioral contract.
