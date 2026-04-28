# Symphony Memory Workflow Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add repo-owned workflow policy, searchable memory, status reporting, consolidation proposals, and deterministic workspace primitives to Harness4Codex.

**Architecture:** Keep the implementation standard-library-only and split by responsibility: workflow parsing, SQLite memory, CLI formatting, orchestration primitives, and hook enrichment. Hooks should enrich context and record history, but never fail closed because memory or workflow parsing failed.

**Tech Stack:** Python standard library, SQLite via `sqlite3`, existing pytest suite, existing Codex hook JSON contract.

---

### Task 1: Workflow Loader

**Files:**
- Create: `harness4codex/workflow.py`
- Test: `tests/test_workflow.py`
- Modify: `harness4codex/hook.py`

- [ ] Write tests for `WORKFLOW.md` discovery, frontmatter parsing, defaults, and prompt rendering.
- [ ] Run `python -m pytest tests/test_workflow.py -q -p no:cacheprovider --basetemp .pytest_tmp_codex` and verify failure from missing module.
- [ ] Implement `WorkflowDefinition`, `find_workflow`, `load_workflow`, and limited YAML frontmatter parsing.
- [ ] Inject workflow context in `UserPromptSubmit` when the payload or process has a repo cwd.
- [ ] Run workflow and hook tests.

### Task 2: SQLite Memory And Consolidation

**Files:**
- Create: `harness4codex/memory.py`
- Test: `tests/test_memory.py`
- Modify: `harness4codex/hook.py`

- [ ] Write tests for history recording, search, proposal storage, and consolidation from `events.jsonl`.
- [ ] Run memory tests and verify failure from missing module.
- [ ] Implement `HarnessMemoryStore`, `MemoryConsolidator`, and `ConsolidationReport`.
- [ ] Record hook history opportunistically from hook handlers.
- [ ] Run memory and hook tests.

### Task 3: CLI Status Surface

**Files:**
- Create: `harness4codex/cli.py`
- Modify: `harness4codex/__main__.py`
- Test: `tests/test_cli.py`

- [ ] Write tests for `status`, `workflow show`, `memory search`, and `memory consolidate`.
- [ ] Run CLI tests and verify failure from missing CLI.
- [ ] Implement `run(argv)` and command handlers that print stable text output.
- [ ] Wire `python -m harness4codex` to the CLI.
- [ ] Run CLI tests.

### Task 4: Orchestration Primitives

**Files:**
- Create: `harness4codex/orchestration.py`
- Test: `tests/test_orchestration.py`
- Modify: `README.md`

- [ ] Write tests for deterministic workspace creation, issue eligibility, and retry backoff.
- [ ] Run orchestration tests and verify failure from missing module.
- [ ] Implement pure data classes and workspace manager without launching Codex.
- [ ] Document that daemon execution is intentionally deferred.
- [ ] Run the full test suite.

### Task 5: Install, Verify, Commit, Push

**Files:**
- Modify: `README.md`

- [ ] Run `python -m pytest tests -q -p no:cacheprovider --basetemp .pytest_tmp_codex`.
- [ ] Run hook smoke tests against the installed hook path with temporary `HARNESS4CODEX_HOME`.
- [ ] Run `python scripts/install.py --source . --codex-home C:\Users\Leonardo\.codex`.
- [ ] Commit with message `Add workflow memory and orchestration primitives`.
- [ ] Push `main` to `origin`.
