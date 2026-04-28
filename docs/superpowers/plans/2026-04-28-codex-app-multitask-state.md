# Codex App Multitask State Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Prevent Harness4Codex state conflicts when Codex app, CLI, or IDE runs multiple local threads/worktrees in parallel.

**Architecture:** Reuse the Harness v3 lesson of owner-aware state locks, but add Codex-specific `session_id + cwd` scoping because Codex hook payloads expose both fields. Store scoped states under `~/.codex/harness/sessions/<scope>/state.json` while retaining legacy singleton fallback for payloads without `session_id`.

**Tech Stack:** Python standard library, existing Codex hooks, pytest.

---

### Task 1: State Scoping

- [x] Add tests proving two sessions in the same repo do not continue each other's active pipeline.
- [x] Add tests proving Stop gate blocks only the matching session.
- [x] Implement `store_for_payload()` and `state_scope_key()`.
- [x] Wire `handle_payload()` to use scoped stores.

### Task 2: Owner-Aware Lock

- [x] Add tests for lock owner file and stale lock replacement.
- [x] Replace file lock with `state.json.lockdir/owner`.
- [x] Preserve timeout and stale cleanup semantics.

### Task 3: Observability

- [x] Add session summary to `harness4codex status`.
- [x] Include `Scope:` in injected HARNESS4CODEX context.
- [x] Make memory consolidation read `sessions/*/events.jsonl`.

### Task 4: Verification

- [x] Run targeted RED tests before implementation.
- [x] Run full pytest suite after implementation.
- [x] Reinstall the updated plugin/skill into `~/.codex`.
