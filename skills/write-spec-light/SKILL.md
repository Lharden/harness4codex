---
name: write-spec-light
description: Use in Harness4Codex L1 feature and refactor pipelines to create a concise test-driving specification.
---

# Write Spec Light for Harness4Codex

Create `docs/specs/{slug}-spec-light.md` from the bundled template. Target 40–80
lines and two to five requirements.

- State objective, user-visible behavior and in-scope files or surfaces.
- Number requirements `REQ-001...`.
- Give every P1 requirement an `AC-001...` in Given/When/Then form.
- Record measurable success criteria and assumptions with evidence/source.
- Use `[NEEDS CLARIFICATION: question]` for a scope-changing ambiguity and open the
  `answer-clarifications` gate; do not fill it by inference.
- Keep implementation choices out unless already constrained by the repository.
- Apply DROP / CONSTRAIN / RETAIN, record artifact type `spec-light`, and advance.

The AC identifiers become test identifiers during TDD.
