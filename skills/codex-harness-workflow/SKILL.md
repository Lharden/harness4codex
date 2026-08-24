---
name: codex-harness-workflow
description: Use when HARNESS4CODEX context appears, when a Codex task is classified as C1/C2/C3/CR/DOCS, when a hook asks to resume a pipeline, or when the user asks for Codex workflow orchestration, proactive skills, hook sequencing, SDD, or Harness4Codex behavior.
---

# Codex Harness Workflow

HARNESS4CODEX is a Codex-native workflow state machine. Treat hook context as routing guidance, not as a substitute for judgment or verification.

## Core Rules

- On Codex hosts, Harness4Codex owns classification, pipeline state, and completion gates.
- Read the `HARNESS4CODEX` context and follow the listed pipeline in order.
- If a referenced skill exists in the current session, use it before doing the work it governs.
- Do not claim completion until `superpowers:verification-before-completion` has fresh evidence from the current turn.
- If hook state and user instructions conflict, the newest user instruction wins; record the conflict in the final summary.
- Do not rely on hooks as the only safety boundary. Apply normal Codex filesystem, git, and approval rules.
- In Codex app multitask workflows, treat `Scope:` in hook context as the active local thread/worktree state. Do not carry pipeline state across scopes.

## Capability Routing

- Treat `HARNESS LITE preview` as advisory routing metadata. Preview happens automatically for `C1+` when `HARNESS_CONTROL_TOKEN` is available; Harness4Codex retains supervision.
- Submit execution to Harness Lite only through an explicit operator opt-in with `HARNESS4CODEX_LITE_EXECUTE=true` and a positive `HARNESS4CODEX_LITE_MAX_COST_USD`.
- When `SCIENCE HARNESS` context appears, use the `science_harness` MCP tools in read-only mode: discover corpora as needed, search claims, retrieve claim evidence, and preserve corpus provenance.

## Pipeline Map

- `C0`: direct answer or small read-only investigation. Escalate if edits touch three or more files.
- `C1`: bug or contained fix. Use `superpowers:systematic-debugging`, then `superpowers:test-driven-development`, then `superpowers:verification-before-completion`.
- `C2`: feature or moderate implementation. Use `superpowers:brainstorming`, `superpowers:writing-plans`, TDD, then verification.
- `C3`: architecture, migration, or broad refactor. Brainstorm, write a plan, implement incrementally with TDD, request review, then verify.
- `CR`: code review. Lead with findings, risks, and test gaps.
- `DOCS`: current API/library behavior. Use `openai-docs` for OpenAI/Codex topics and primary official documentation for other libraries.

## Stop Gate

When the Stop hook blocks, continue the task instead of ending the turn. Run the missing verification or explain the blocker with evidence.
