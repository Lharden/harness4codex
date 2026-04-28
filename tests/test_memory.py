import json

from harness4codex.memory import HarnessMemoryStore, MemoryConsolidator


def test_memory_records_and_searches_history(tmp_path):
    store = HarnessMemoryStore(tmp_path)

    store.record_history("UserPromptSubmit", "Corrija bug de login", {"level": "C1"})
    results = store.search("login")

    assert len(results) == 1
    assert results[0]["event"] == "UserPromptSubmit"
    assert results[0]["metadata"]["level"] == "C1"


def test_memory_remember_upserts_by_scope_kind_key(tmp_path):
    store = HarnessMemoryStore(tmp_path)

    store.remember("repo:harness4codex", "fact", "tests", "pytest -q", "manual")
    store.remember("repo:harness4codex", "fact", "tests", "python -m pytest", "manual")
    memories = store.list_memories(scope="repo:harness4codex", kind="fact")

    assert len(memories) == 1
    assert memories[0]["value"] == "python -m pytest"


def test_consolidator_creates_auditable_proposals_without_editing_files(tmp_path):
    events = [
        {"event": "PreToolUse", "payload": {"command": "git reset --hard HEAD~1"}},
        {"event": "PostToolUse", "payload": {"files": ["a.py", "b.py", "c.py", "d.py"]}},
        {"event": "Stop", "payload": {"blocked": True, "reason": "verification gate"}},
    ]
    with (tmp_path / "events.jsonl").open("w", encoding="utf-8") as handle:
        for event in events:
            handle.write(json.dumps(event) + "\n")

    report = MemoryConsolidator(tmp_path).consolidate()
    proposals = HarnessMemoryStore(tmp_path).list_memories(kind="proposal")

    assert report.events_read == 3
    assert {proposal["key"] for proposal in proposals} >= {
        "git-guardrail-review",
        "workflow-verification-reminder",
        "large-edit-workflow-review",
    }
    assert not (tmp_path / "skills").exists()


def test_consolidator_records_summary_history(tmp_path):
    (tmp_path / "events.jsonl").write_text(
        json.dumps({"event": "UserPromptSubmit", "payload": {"prompt": "Implemente CSV"}}) + "\n",
        encoding="utf-8",
    )

    MemoryConsolidator(tmp_path).consolidate()
    results = HarnessMemoryStore(tmp_path).search("consolidated")

    assert results
    assert results[0]["event"] == "MemoryConsolidation"


def test_consolidator_reads_session_event_logs(tmp_path):
    session_dir = tmp_path / "sessions" / "s-abc"
    session_dir.mkdir(parents=True)
    (session_dir / "events.jsonl").write_text(
        json.dumps({"event": "Stop", "payload": {"blocked": True, "reason": "verification gate"}}) + "\n",
        encoding="utf-8",
    )

    report = MemoryConsolidator(tmp_path).consolidate()
    proposals = HarnessMemoryStore(tmp_path).list_memories(kind="proposal")

    assert report.events_read == 1
    assert [proposal["key"] for proposal in proposals] == ["workflow-verification-reminder"]
