---
name: write-spec
description: Use in Harness4Codex L2 pipelines to write a complete behavioral specification with stories, traceable acceptance criteria and explicit ambiguities.
---

# Write Spec for Harness4Codex

Write `docs/specs/{slug}-spec.md` using the bundled template.

1. Derive the positive scope from `docs/CONTEXT.md`, graph evidence and confirmed
   prior decisions.
2. Define independently testable P1/P2/P3 user stories.
3. Number all requirements and Given/When/Then acceptance criteria; each AC must be
   observable without knowing the future implementation.
4. Declare boundaries, data constraints, failure behavior, success metrics and an
   assumption ledger with evidence and the REQ/AC each assumption justifies.
5. Mark scope-changing ambiguity `[NEEDS CLARIFICATION: ...]` and open a human gate.
6. Run the editorial gate, record artifact type `spec`, then transition to `grill-me`.

The spec states what must hold. Architecture and API mechanics belong in `design-doc`.
