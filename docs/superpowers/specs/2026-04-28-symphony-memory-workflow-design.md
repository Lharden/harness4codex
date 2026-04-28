# Symphony Memory Workflow Design

## Context

Harness4Codex currently provides Codex hooks, task classification, a local state machine, git guardrails, and a workflow skill. The next useful step is to move from session-only guidance toward repo-owned workflow policy and durable learning surfaces.

The OpenAI Symphony spec argues for a small orchestration layer with repo-owned `WORKFLOW.md`, deterministic workspaces, explicit state, retries, and observable logs. Self-evolving-agent writeups point in the same direction for memory: keep hot context small, store warm searchable history, consolidate long-running patterns, and propose skill/workflow updates rather than silently mutating behavior.

## Goals

- Load a repo-local `WORKFLOW.md` contract and inject its relevant guidance into Harness4Codex hook context.
- Store searchable history and reusable memories in SQLite under the harness home.
- Consolidate hook/event history into audit-friendly proposals.
- Add a `harness4codex status` CLI surface.
- Add deterministic workspace primitives for a later Symphony-style issue orchestrator.

## Non-Goals

- No autonomous daemon that launches Codex without an explicit command.
- No auto-merge, auto-push, or silent skill mutation.
- No Linear/GitHub API polling in this phase.
- No dependency on a third-party YAML parser.

## Architecture

- `harness4codex.workflow` finds and parses `WORKFLOW.md` using a small YAML-frontmatter subset and exposes typed defaults.
- `harness4codex.memory` stores history, memories, and proposals in SQLite, then consolidates JSONL events into operator-reviewable reports.
- `harness4codex.cli` exposes `status`, `workflow show`, `memory search`, and `memory consolidate`.
- `harness4codex.orchestration` contains pure workspace/state primitives that can later back an issue tracker daemon.
- `harness4codex.hook` enriches prompt context with `WORKFLOW.md` when available and records hook history in memory without blocking if memory writes fail.

## Safety

Consolidation writes proposals to the memory database only. It does not edit skills, hooks, workflow files, or git state. Any future self-update flow must produce a diff for review.
