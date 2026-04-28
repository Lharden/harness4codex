import json
import os
import time

from harness4codex.classifier import Classification
from harness4codex.state import HarnessStateStore, store_for_payload


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


def test_store_for_payload_scopes_by_session_and_cwd(tmp_path):
    repo = tmp_path / "repo"
    repo.mkdir()

    a = store_for_payload({"session_id": "session-a", "cwd": str(repo)}, tmp_path)
    b = store_for_payload({"session_id": "session-b", "cwd": str(repo)}, tmp_path)

    assert a.home != b.home
    assert a.home.parent == b.home.parent == tmp_path / "sessions"
    assert "session-a" not in str(a.home)
    assert a.scope is not None


def test_store_for_payload_without_session_uses_legacy_home(tmp_path):
    store = store_for_payload({"cwd": str(tmp_path)}, tmp_path)

    assert store.home == tmp_path
    assert store.scope is None


def test_state_lock_records_owner_and_releases_only_own_lock(tmp_path):
    store = HarnessStateStore(tmp_path)

    with store._lock():  # noqa: SLF001 - validating lock primitive behavior
        assert store.lock_path.exists()
        assert store.lock_owner_path.exists()
        owner_pid = store.lock_owner_path.read_text(encoding="utf-8").split()[0]
        assert owner_pid == str(os.getpid())

    assert not store.lock_path.exists()


def test_state_lock_replaces_stale_lock(tmp_path):
    store = HarnessStateStore(tmp_path)
    store.lock_path.mkdir(parents=True)
    store.lock_owner_path.write_text("999999 0\n", encoding="utf-8")
    old = time.time() - 60
    os.utime(store.lock_path, (old, old))

    with store._lock(timeout=1.0):
        owner_pid = store.lock_owner_path.read_text(encoding="utf-8").split()[0]
        assert owner_pid == str(os.getpid())

    assert not store.lock_path.exists()
