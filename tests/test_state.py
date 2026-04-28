import json

from harness4codex.classifier import Classification
from harness4codex.state import HarnessStateStore


def test_state_initializes_idle(tmp_path):
    store = HarnessStateStore(tmp_path)

    state = store.load()

    assert state["status"] == "idle"
    assert (tmp_path / "state.json").exists()


def test_start_task_persists_classification(tmp_path):
    store = HarnessStateStore(tmp_path)
    classification = Classification(
        level="C2",
        kind="feature",
        pipeline=["codex-spec-light", "verification-before-completion"],
        reasons=["feature keyword"],
        is_task_switch=False,
    )

    state = store.start_task(classification, "implemente exportacao")

    assert state["status"] == "active"
    assert state["level"] == "C2"
    assert state["pipeline"] == ["codex-spec-light", "verification-before-completion"]


def test_recording_files_promotes_simple_question(tmp_path):
    store = HarnessStateStore(tmp_path)
    store.start_task(
        Classification("C0", "question", [], ["simple"], False),
        "qual arquivo devo editar?",
    )

    store.record_file("a.py")
    store.record_file("b.py")
    state = store.record_file("c.py")

    assert state["level"] == "C1"
    assert state["status"] == "active"
    assert "verification-before-completion" in state["pipeline"]


def test_event_log_appends_json_lines(tmp_path):
    store = HarnessStateStore(tmp_path)

    store.log_event("UserPromptSubmit", {"prompt": "x"})
    store.log_event("Stop", {"verified": False})

    lines = (tmp_path / "events.jsonl").read_text(encoding="utf-8").splitlines()
    assert [json.loads(line)["event"] for line in lines] == ["UserPromptSubmit", "Stop"]


def test_mark_verified_records_command(tmp_path):
    store = HarnessStateStore(tmp_path)
    store.start_task(Classification("C1", "bug", ["verification-before-completion"], [], False), "fix")

    state = store.mark_verified("pytest -q")

    assert state["verified"] is True
    assert state["last_verification"]["command"] == "pytest -q"
