from harness4codex.classifier import Classification
from harness4codex.cli import run
from harness4codex.memory import HarnessMemoryStore
from harness4codex.state import HarnessStateStore, store_for_payload
from harness4codex.state_db import HarnessDatabase


def test_status_prints_state_workflow_and_memory_count(tmp_path, capsys):
    home = tmp_path / "home"
    repo = tmp_path / "repo"
    repo.mkdir()
    (repo / "WORKFLOW.md").write_text("---\nproject: Demo\n---\n# Workflow\n", encoding="utf-8")
    HarnessStateStore(home).load()
    HarnessMemoryStore(home).record_history("UserPromptSubmit", "hello", {})

    exit_code = run(["status", "--home", str(home), "--cwd", str(repo)])

    output = capsys.readouterr().out
    assert exit_code == 0
    assert "Harness4Codex status" in output
    assert "status: idle" in output
    assert "workflow: " in output
    assert "memory records: 1" in output


def test_status_prints_isolated_session_summary(tmp_path, capsys):
    home = tmp_path / "home"
    store_for_payload({"session_id": "session-a", "cwd": str(tmp_path)}, home).start_task(
        Classification("C2", "feature", ["codex-spec-light"], [], False),
        "implemente csv",
    )

    exit_code = run(["status", "--home", str(home), "--cwd", str(tmp_path)])

    output = capsys.readouterr().out
    assert exit_code == 0
    assert "sessions: 1" in output
    assert "active sessions: 1" in output


def test_workflow_show_prints_rendered_context(tmp_path, capsys):
    repo = tmp_path / "repo"
    repo.mkdir()
    (repo / "WORKFLOW.md").write_text(
        "---\nverification:\n  commands:\n    - pytest -q\n---\n# Workflow\nReview first.\n",
        encoding="utf-8",
    )

    exit_code = run(["workflow", "show", "--cwd", str(repo)])

    assert exit_code == 0
    output = capsys.readouterr().out
    assert "Repo WORKFLOW.md" in output
    assert "pytest -q" in output


def test_memory_search_prints_matches(tmp_path, capsys):
    home = tmp_path / "home"
    HarnessMemoryStore(home).record_history("UserPromptSubmit", "login bug", {"level": "C1"})

    exit_code = run(["memory", "search", "login", "--home", str(home)])

    output = capsys.readouterr().out
    assert exit_code == 0
    assert "UserPromptSubmit" in output
    assert "login bug" in output


def test_memory_consolidate_prints_proposals(tmp_path, capsys):
    home = tmp_path / "home"
    home.mkdir()
    (home / "events.jsonl").write_text('{"event":"Stop","payload":{"blocked":true}}\n', encoding="utf-8")

    exit_code = run(["memory", "consolidate", "--home", str(home)])

    output = capsys.readouterr().out
    assert exit_code == 0
    assert "events read: 1" in output
    assert "workflow-verification-reminder" in output


def test_doctor_json_prints_machine_readiness(tmp_path, capsys):
    (tmp_path / "config.toml").write_text("[features]\nhooks = false\n", encoding="utf-8")

    exit_code = run(["doctor", "--home", str(tmp_path), "--json"])

    output = capsys.readouterr().out
    assert exit_code == 1
    assert '"ok": false' in output
    assert "HOOKS_DISABLED" in output


def test_lite_submit_refuses_without_explicit_execution_opt_in(tmp_path, capsys, monkeypatch):
    monkeypatch.delenv("HARNESS4CODEX_LITE_EXECUTE", raising=False)
    monkeypatch.delenv("HARNESS4CODEX_LITE_MAX_COST_USD", raising=False)

    exit_code = run(["lite", "submit", "Implementar CSV", "--cwd", str(tmp_path), "--level", "C2"])

    output = capsys.readouterr().out
    assert exit_code == 2
    assert "opt-in" in output


def test_classification_confirm_updates_transactional_task(tmp_path, capsys):
    store = HarnessStateStore(tmp_path)
    state = store.start_task(
        Classification("C2", "feature", ["write-spec-light", "tdd", "verify-against-spec"], [], False), "build"
    )

    exit_code = run(
        [
            "classification",
            "confirm",
            "--home",
            str(tmp_path),
            "--task",
            state["task_id"],
            "--tier",
            "L2",
            "--kind",
            "feature",
            "--confidence",
            "0.9",
        ]
    )

    assert exit_code == 0
    assert "L2-feature" in capsys.readouterr().out
    assert HarnessDatabase(tmp_path).task(state["task_id"])["phase"] == "discuss"


def test_task_artifact_evidence_and_completion_commands_drive_fsm(tmp_path, capsys):
    store = HarnessStateStore(tmp_path)
    state = store.start_task(
        Classification("C2", "feature", ["write-spec-light", "tdd", "verify-against-spec"], [], False), "build"
    )

    assert (
        run(
            [
                "artifact",
                "record",
                "--home",
                str(tmp_path),
                "--task",
                state["task_id"],
                "--type",
                "spec-light",
                "--path",
                "docs/specs/demo-spec-light.md",
                "--hash",
                "abc",
            ]
        )
        == 0
    )
    state = HarnessDatabase(tmp_path).task(state["task_id"])
    assert (
        run(
            [
                "task",
                "transition",
                "--home",
                str(tmp_path),
                "--task",
                state["task_id"],
                "--to",
                "tdd",
                "--expect-revision",
                str(state["revision"]),
            ]
        )
        == 0
    )
    state = HarnessDatabase(tmp_path).task(state["task_id"])
    assert (
        run(
            [
                "task",
                "transition",
                "--home",
                str(tmp_path),
                "--task",
                state["task_id"],
                "--to",
                "verify-against-spec",
                "--expect-revision",
                str(state["revision"]),
            ]
        )
        == 0
    )
    assert (
        run(
            [
                "evidence",
                "record",
                "--home",
                str(tmp_path),
                "--task",
                state["task_id"],
                "--type",
                "test",
                "--command",
                "pytest -q",
                "--exit-code",
                "0",
                "--tests-collected",
                "5",
                "--tests-passed",
                "5",
                "--output-hash",
                "out",
            ]
        )
        == 0
    )
    state = HarnessDatabase(tmp_path).task(state["task_id"])
    assert (
        run(
            [
                "task",
                "complete",
                "--home",
                str(tmp_path),
                "--task",
                state["task_id"],
                "--expect-revision",
                str(state["revision"]),
            ]
        )
        == 0
    )

    assert HarnessDatabase(tmp_path).task(state["task_id"])["status"] == "done"
    assert "done" in capsys.readouterr().out


def test_task_transition_cli_rejects_stale_revision(tmp_path, capsys):
    store = HarnessStateStore(tmp_path)
    state = store.start_task(Classification("C1", "bug", ["systematic-debugging", "tdd", "verify"], [], False), "fix")

    exit_code = run(
        [
            "task",
            "transition",
            "--home",
            str(tmp_path),
            "--task",
            state["task_id"],
            "--to",
            "tdd",
            "--expect-revision",
            "999",
        ]
    )

    assert exit_code == 2
    assert "revision mismatch" in capsys.readouterr().out


def test_contract_check_cli_reports_conformance(capsys):
    exit_code = run(["contract", "check", "--json"])

    output = capsys.readouterr().out
    assert exit_code == 0
    assert '"conformant": true' in output
    assert '"adapter": "harness4codex"' in output


def test_memory_compress_and_wiki_cli(tmp_path, capsys):
    memory = tmp_path / "recent.md"
    memory.write_text("Basically, I think this is ready.\n", encoding="utf-8")
    assert run(["memory", "compress", str(memory)]) == 0
    assert "saved_chars" in capsys.readouterr().out

    vault = tmp_path / "AI-Brain"
    vault.mkdir()
    (vault / "decision.md").write_text("# Storage\nSQLite WAL is durable.\n", encoding="utf-8")
    assert run(["wiki", "build", "--root", str(vault)]) == 0
    assert run(["wiki", "query", "SQLite durable", "--root", str(vault)]) == 0
    assert "[[decision]]" in capsys.readouterr().out


def test_branch_cli_offer_approve_open_and_list(tmp_path, capsys):
    db = HarnessDatabase(tmp_path)
    task = db.start_task(
        scope_id="s",
        legacy_level="C2",
        tier="L2",
        kind="feature",
        pipeline=["discuss", "tdd"],
        prompt="branch",
    )
    assert (
        run(
            [
                "branch",
                "offer",
                "--home",
                str(tmp_path),
                "--task",
                task["task_id"],
                "--name",
                "Graph retrieval",
                "--topic",
                "independent graph retrieval",
                "--turn",
                "10",
            ]
        )
        == 0
    )
    offered = db.list_branches(task["task_id"])[0]
    assert run(["branch", "approve", "--home", str(tmp_path), "--branch", offered["branch_id"]]) == 0
    seed = tmp_path / "seed.md"
    seed.write_text("Investigate graph retrieval", encoding="utf-8")
    assert (
        run(
            [
                "branch",
                "open",
                "--home",
                str(tmp_path),
                "--branch",
                offered["branch_id"],
                "--seed",
                str(seed),
            ]
        )
        == 0
    )
    assert run(["branch", "list", "--home", str(tmp_path), "--task", task["task_id"]]) == 0
    output = capsys.readouterr().out
    assert '"status": "open"' in output
    assert '"codex"' in output and '"fork"' in output
