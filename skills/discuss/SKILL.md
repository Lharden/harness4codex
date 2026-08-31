---
name: discuss
description: Use in Harness4Codex L2 pipelines to turn an ambiguous objective into compact, positive decision context before specification.
---

# Discuss for Harness4Codex

Establish what will be built before selecting implementation details.

1. Read repo instructions, active task context and relevant prior decisions through
   `wiki-query`; use `graph-context` for current code structure.
2. Restate the positive objective, users, success signal and operational boundary.
3. Identify only decisions that materially change behavior, API, data or rollout.
4. Ask the user for unresolved choices one at a time when assumptions would change
   scope. Mark them `[NEEDS CLARIFICATION: ...]` until answered.
5. Write `docs/CONTEXT.md` with Objective, Confirmed Decisions, Constraints,
   Discretion and Open Clarifications. Keep it short and cite prior-art pages.
6. Apply the Harness4Codex DROP / CONSTRAIN / RETAIN gate before saving. Rejected
   editorial directions leave no thematic controller or memory entry.
7. Record the context artifact, then transition to the next phase.

Output is a decision surface for `brainstorming` and `write-spec`, not a design doc.
