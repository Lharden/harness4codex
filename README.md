# Harness4Codex

Harness4Codex is a contract-backed Codex workflow supervisor. It combines full-lifecycle hooks, scoped transactional state, SDD v3 skills, human gates, evidence, Graphify context, operational memory and bounded external capabilities.

## What it adds

- Deterministic classification with semantic confirmation and human override, normalized to `L0/L1/L2 + kind` while preserving legacy Codex labels.
- SQLite WAL state under `~/.codex/harness`, isolated by session, repository and worktree, with revision CAS, leases and fencing.
- Active scoped pipelines auto-abandon after `HARNESS4CODEX_PIPELINE_TTL_H` hours (default `24`), releasing the scope and recording a transactional expiry event.
- Context injection that asks Codex to use `codex-harness-workflow`.
- SDD v3 pipelines with light/full specs, adversarial review, design docs, plan validation, TDD and item-by-item spec verification.
- Human approval gates for specs, plans, clarifications, branches and bounded escalation.
- Parsed command policy for destructive Git operations and Codex plugin mutations.
- Revision-bound verification evidence and bounded continuation on `Stop`.
- Repo-local `WORKFLOW.md` discovery for versioned workflow policy.
- FTS5 operational memory, cited AI-Brain wiki search and reversible secondary-memory compression.
- Graphify freshness/provenance artifacts and degraded structural fallback.
- Capability arsenal with closed vocabulary, overlap and budget checks.
- Persistent conversation Branch Keeper with approval, parking, recall and close.
- Structured multi-agent node census and `NodeResult` reconciliation.
- Vendored Harness4Contract snapshot with machine-readable conformance reports.
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
2. Installs the packaged Harness4Codex skills.
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
python -m harness4codex memory compress recent.md --dry-run
python -m harness4codex wiki build --root "$env:VAULT_PATH\AI-Brain"
python -m harness4codex wiki query "durable pipeline state" --root "$env:VAULT_PATH\AI-Brain"
python -m harness4codex contract check --json
python -m harness4codex graph context --task TASK --scope SCOPE --query "affected components"
python -m harness4codex branch list --home "$HOME\.codex\harness" --task TASK
python -m harness4codex doctor --json
python -m harness4codex lite preview "Implementar CSV" --level C2
```

`branch open` reads its approved seed file and emits the locally supported
`codex fork [SESSION_ID|--last] [PROMPT]` argument vector. Pass `--session` to
fork an exact Codex session; otherwise the most recent session is used.

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
