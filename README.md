# Harness4Codex

Harness4Codex is a Codex-native workflow harness inspired by Harness v3 for Claude Code.

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
- Idempotent installer for `~/.codex/config.toml`, `~/.codex/hooks.json`, the plugin folder, and the direct skill folder.

## Install

From a local checkout:

```powershell
python scripts/install.py --source .
```

Or on PowerShell:

```powershell
.\scripts\install.ps1
```

The installer:

1. Copies the plugin to `~/.codex/plugins/harness4codex`.
2. Copies the skill to `~/.codex/skills/codex-harness-workflow`.
3. Enables `[features] codex_hooks = true`.
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
```

`memory consolidate` creates auditable proposals in SQLite. It does not edit skills, hooks, workflow files, or git state.

## Notes

Codex hooks are still an evolving interface. Harness4Codex installs global hooks because current Codex builds are more reliable with `~/.codex/hooks.json` than plugin-local hook discovery.
