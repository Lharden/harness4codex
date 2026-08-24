# Harness4Codex

Harness4Codex is the Codex-native workflow supervisor. It combines Codex hooks, scoped state, skills, and guardrails while exposing Harness Lite and Science Harness as bounded capabilities.

It uses Codex hooks, a local state machine, a workflow skill, and git guardrails. It does not write to `~/.claude` and does not assume Claude Code hook semantics.

## What it adds

- Prompt classification into `C0`, `C1`, `C2`, `C3`, `CR`, and `DOCS`.
- Persistent state under `~/.codex/harness`.
- Context injection that asks Codex to use `codex-harness-workflow`.
- Git guardrails for `git push --force`, `git reset --hard`, `git clean -f`, and similar commands.
- Verification gate on `Stop` for active implementation pipelines.
- Repo-local `WORKFLOW.md` discovery for versioned workflow policy.
- SQLite-backed searchable memory and consolidation proposals under `~/.codex/harness`.
- CLI commands for status, workflow inspection, and memory search/consolidation.
- Deterministic workspace primitives for future Symphony-style issue orchestration.
- Codex app multitask safety: hook state is isolated by `session_id + cwd`, with atomic owner locks for each scoped state file.
- Automatic advisory Harness Lite route preview for `C1+` when its control token is configured.
- Explicit opt-in Harness Lite execution with a positive cost budget.
- Automatic Science Harness evidence intent, routed through the read-only `science_harness` MCP server.
- `doctor` checks for hook/plugin drift, MCP readiness, Codex Apps, and inherited Obsidian credentials.

## Install

From a local checkout:

```powershell
python scripts/install.py --source .
```

Or on PowerShell:

```powershell
.\scripts\install.ps1
```

The compatibility installer:

1. Copies the plugin to `~/.codex/plugins/harness4codex`.
2. Copies the skill to `~/.codex/skills/codex-harness-workflow`.
3. Enables `[features] hooks = true`.
4. Merges Harness4Codex entries into `~/.codex/hooks.json`.

Start a new Codex session after installing so the hook configuration is loaded.

## Validate

```powershell
python -m pytest
python hooks/codex_harness_hook.py
```

For the hook script, Codex normally sends JSON on stdin. Unit tests cover the supported event payloads directly.

## Workflow Policy

Add a `WORKFLOW.md` at a repo root to give Codex versioned local policy:

```markdown
---
project: Example
verification:
  commands:
    - python -m pytest
handoff_state: Human Review
---
# Workflow
Make small changes, run the listed verification, and attach proof before review.
```

Harness4Codex injects a compact rendering of this file into `UserPromptSubmit` hook context.

## CLI

```powershell
python -m harness4codex status
python -m harness4codex workflow show
python -m harness4codex memory search verification
python -m harness4codex memory consolidate
python -m harness4codex doctor --json
python -m harness4codex lite preview "Implementar CSV" --level C2
```

Harness Lite submission is deliberately separate from preview:

```powershell
$env:HARNESS4CODEX_LITE_EXECUTE = "true"
$env:HARNESS4CODEX_LITE_MAX_COST_USD = "1.50"
python -m harness4codex lite submit "Implementar CSV" --level C2
```

`memory consolidate` creates auditable proposals in SQLite. It does not edit skills, hooks, workflow files, or git state.

## Codex App Multitask Safety

Codex hook payloads include `session_id` and `cwd`. Harness4Codex uses those fields to store each active app/CLI/IDE thread under:

```text
~/.codex/harness/sessions/<scope>/state.json
```

This prevents one local Codex app thread or worktree from continuing, blocking, or verifying another thread's pipeline. If a hook payload does not include `session_id`, Harness4Codex falls back to the legacy singleton `~/.codex/harness/state.json`.

Each scoped state file uses an atomic lock file with an owner token and stale-lock cleanup. Session history is written to one WAL-backed SQLite store so the CLI can query all scopes.

## Notes

The plugin uses Codex's conventional `hooks/hooks.json` discovery and the current hook output schemas. Keep one workflow supervisor enabled per host and restart Codex after changing process-level MCP credentials.
