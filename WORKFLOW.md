---
project: Harness4Codex
verification:
  commands:
    - python -m pytest tests -q -p no:cacheprovider --basetemp .pytest_tmp_codex
handoff_state: Human Review
orchestration:
  active_states:
    - Ready
    - In Progress
  terminal_states:
    - Done
    - Canceled
  max_turns: 5
---
# Harness4Codex Workflow

Keep changes small and test-first. Hooks may route the work, but they are not a safety boundary.

Before finalizing implementation work:

- Run the verification command listed in frontmatter.
- Use temporary harness homes for hook smoke tests so fake task state is not left active.
- Use the plugin marketplace flow for active Codex installations; keep `scripts/install.py` for compatibility deployments.
- Consolidation may create memory proposals, but it must not silently edit skills, hooks, or git state.
- Harness Lite preview is advisory; execution requires explicit opt-in and a positive budget.
- Science Harness access is read-only through its MCP server.
