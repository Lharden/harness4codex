---
name: branch-out
description: Use when Harness4Codex detects a valuable conversation tangent, drift, or an explicit branch request and the idea needs reversible parking.
---

# Branch Out for Harness4Codex

Commands are `offer`, `open`, `list`, `recall`, `close`, and `drift` through
`harness4codex branch ...`.

- Offer a specific two-to-four-word branch once, explaining its independent value.
- Opening requires explicit user approval through the `branch-open` gate.
- Write a seed from the bundled template using paths and decisions, not copied files.
- `open` creates a persistent branch record and produces a `codex fork` launch command;
  launch only after approval. Park the topic in the parent.
- `recall` restores the topic; `close` records a short conclusion for the parent.
- `drift` reanchors or offers a branch without launching another session.

Default limits: three open branches, two offers per session, eight-turn cooldown and
semantic deduplication. Branch records are scoped to the parent task/worktree.
