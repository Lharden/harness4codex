---
name: codex-harness-workflow
description: Use when HARNESS4CODEX context appears, when a Codex task is classified as C1/C2/C3/CR/DOCS, when a hook asks to resume a pipeline, or when the user asks for Codex workflow orchestration, proactive skills, hook sequencing, SDD, or Harness4Codex behavior.
---

# Codex Harness Workflow

HARNESS4CODEX is a Codex-native workflow state machine. Treat hook context as routing guidance, not as a substitute for judgment or verification.

## Core Rules

- Read the `HARNESS4CODEX` context and follow the listed pipeline in order.
- If a referenced skill exists in the current session, use it before doing the work it governs.
- Do not claim completion until `verification-before-completion` has fresh evidence from the current turn.
- If hook state and user instructions conflict, the newest user instruction wins; record the conflict in the final summary.
- Do not rely on hooks as the only safety boundary. Apply normal Codex filesystem, git, and approval rules.
- In Codex app multitask workflows, treat `Scope:` in hook context as the active local thread/worktree state. Do not carry pipeline state across scopes.

## Pipeline Map

- `C0`: direct answer or small read-only investigation. Escalate if edits touch three or more files.
- `C1`: bug or contained fix. Use systematic debugging, then TDD where feasible, then verification.
- `C2`: feature or moderate implementation. Produce a light spec, implement in small slices, verify.
- `C3`: architecture, migration, or broad refactor. Design first, write a plan, implement incrementally, request review, verify.
- `CR`: code review. Lead with findings, risks, and test gaps.
- `DOCS`: current API/library behavior. Use official docs or the relevant docs skill before committing to details.

## Stop Gate

When the Stop hook blocks, continue the task instead of ending the turn. Run the missing verification or explain the blocker with evidence.
