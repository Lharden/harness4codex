from harness4codex.classifier import Classification
from harness4codex.cli import run
from harness4codex.memory import HarnessMemoryStore
from harness4codex.state import HarnessStateStore, store_for_payload


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
