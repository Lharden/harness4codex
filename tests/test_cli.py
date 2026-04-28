from harness4codex.cli import run
from harness4codex.memory import HarnessMemoryStore
from harness4codex.state import HarnessStateStore


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
