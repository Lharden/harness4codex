# Harness4Codex implementation plan

Goal: provide a Codex-native workflow harness inspired by Harness v3 for Claude Code, but designed around Codex hooks, skills, plugins, and state stored under `~/.codex/harness`.

## Scope

- Python hook runtime with no third-party dependencies.
- Prompt classifier for workflow level selection.
- State machine with active task, pipeline, files touched, verification gate, and event log.
- Git guard for high-risk commands.
- Codex plugin metadata and direct skill package.
- Idempotent installer that enables `features.codex_hooks`, merges `~/.codex/hooks.json`, and copies plugin/skill assets.
- Test suite covering classifier, state, hook outputs, packaging, and install helpers.

## Non-goals

- No Claude Code files or `~/.claude` paths.
- No hidden destructive behavior.
- No long-running external validation in tests.
- No claim that Codex has a `PreCompact` equivalent.

## Validation

1. Red tests before implementation.
2. Focused pytest suite after implementation.
3. Hook smoke tests through direct Python invocation.
4. Install dry-run/unit tests before writing to `~/.codex`.
