from __future__ import annotations

import pytest

from harness4codex.contract import ContractSnapshot
from harness4codex.state_db import HarnessDatabase, StateTransitionError


def _start(db: HarnessDatabase, scope: str = "scope-a", level: str = "C2", kind: str = "feature"):
    contract = ContractSnapshot.load()
    normalized = contract.normalize(level, kind)
    return db.start_task(
        scope_id=scope,
        legacy_level=level,
        tier=normalized["tier"],
        kind=normalized["kind"],
        pipeline=contract.pipeline(normalized["tier"], normalized["kind"]),
        prompt="implement feature",
    )


def test_database_starts_one_scoped_task_with_formal_phase(tmp_path):
    db = HarnessDatabase(tmp_path)

    task = _start(db)

    assert task["scope_id"] == "scope-a"
    assert task["tier"] == "L1"
    assert task["kind"] == "feature"
    assert task["phase"] == "write-spec-light"
    assert task["status"] == "active"
    assert db.current_task("scope-a")["task_id"] == task["task_id"]


def test_starting_a_new_task_abandons_the_previous_task_in_same_scope(tmp_path):
    db = HarnessDatabase(tmp_path)
    first = _start(db)

    second = _start(db)

    assert second["task_id"] != first["task_id"]
    assert db.task(first["task_id"])["status"] == "abandoned"
    assert db.current_task("scope-a")["task_id"] == second["task_id"]


def test_transition_requires_phase_artifact_and_rejects_skips(tmp_path):
    db = HarnessDatabase(tmp_path)
    task = _start(db)

    with pytest.raises(StateTransitionError, match="next phase"):
        db.transition(task["task_id"], "verify-against-spec", expected_revision=task["revision"])
    with pytest.raises(StateTransitionError, match="artifact"):
        db.transition(task["task_id"], "tdd", expected_revision=task["revision"])

    task = db.record_artifact(task["task_id"], "spec-light", "docs/specs/demo-spec-light.md", "abc")
    task = db.transition(task["task_id"], "tdd", expected_revision=task["revision"])

    assert task["phase"] == "tdd"


def test_human_gate_sets_awaiting_gate_and_resolution_advances(tmp_path):
    db = HarnessDatabase(tmp_path)
    task = _start(db, level="C3", kind="architecture")
    for next_phase, artifact in [
        ("brainstorming", None),
        ("graph-context", None),
        ("write-spec", ("graph-context", "docs/specs/graph-context.json")),
        ("grill-me", ("spec", "docs/specs/demo-spec.md")),
        ("approve-spec", None),
    ]:
        if artifact:
            task = db.record_artifact(task["task_id"], artifact[0], artifact[1], "hash")
        task = db.transition(task["task_id"], next_phase, expected_revision=task["revision"])

    assert task["status"] == "awaiting_gate"
    assert task["pending_gate"] == "approve-spec"

    task = db.resolve_gate(task["task_id"], "approve-spec", "approve", expected_revision=task["revision"])

    assert task["status"] == "active"
    assert task["phase"] == "design-doc"


def test_fresh_test_evidence_allows_completion_and_file_change_invalidates_it(tmp_path):
    db = HarnessDatabase(tmp_path)
    task = _start(db, level="C1", kind="bug")
    task = db.transition(task["task_id"], "tdd", expected_revision=task["revision"])
    task = db.transition(task["task_id"], "verify", expected_revision=task["revision"])
    task = db.record_evidence(
        task["task_id"],
        evidence_type="test",
        command="pytest -q",
        exit_code=0,
        tests_collected=4,
        tests_passed=4,
        output_hash="out",
    )

    assert task["verified"] is True
    task = db.complete(task["task_id"], expected_revision=task["revision"])
    assert task["status"] == "done"

    next_task = _start(db)
    next_task = db.record_evidence(
        next_task["task_id"],
        evidence_type="test",
        command="pytest -q",
        exit_code=0,
        tests_collected=1,
        tests_passed=1,
        output_hash="out-2",
    )
    next_task = db.touch_file(next_task["task_id"], "app.py")
    assert next_task["verified"] is False
    with pytest.raises(StateTransitionError, match="fresh verification"):
        db.complete(next_task["task_id"], expected_revision=next_task["revision"])


def test_zero_collected_tests_are_not_verification(tmp_path):
    db = HarnessDatabase(tmp_path)
    task = _start(db, level="C1", kind="bug")

    task = db.record_evidence(
        task["task_id"],
        evidence_type="test",
        command="pytest -q",
        exit_code=0,
        tests_collected=0,
        tests_passed=0,
        output_hash="empty",
    )

    assert task["verified"] is False


def test_semantic_confirmation_records_provenance_and_replaces_pipeline(tmp_path):
    db = HarnessDatabase(tmp_path)
    task = _start(db, level="C2", kind="feature")

    initial = db.classification(task["task_id"])
    assert initial["suggested"] == "L1-feature"
    assert initial["final"] is None

    task = db.confirm_classification(
        task["task_id"],
        tier="L2",
        kind="feature",
        pipeline=ContractSnapshot.load().pipeline("L2", "feature"),
        source="semantic",
        confidence=0.91,
    )

    decision = db.classification(task["task_id"])
    assert task["tier"] == "L2"
    assert task["phase"] == "discuss"
    assert decision == {
        "suggested": "L1-feature",
        "final": "L2-feature",
        "source": "semantic",
        "confidence": 0.91,
        "agreed": False,
    }


def test_lease_takeover_increments_fencing_epoch_and_rejects_old_owner(tmp_path):
    db = HarnessDatabase(tmp_path)
    task = _start(db, level="C1", kind="bug")
    first = db.acquire_lease("scope-a", "owner-a", ttl_seconds=10, now=100)
    second = db.acquire_lease("scope-a", "owner-b", ttl_seconds=10, now=111)

    assert first["owner_epoch"] == 1
    assert second["owner_epoch"] == 2
    with pytest.raises(StateTransitionError, match="owner epoch"):
        db.transition(
            task["task_id"],
            "tdd",
            expected_revision=db.task(task["task_id"])["revision"],
            owner_epoch=first["owner_epoch"],
        )

    task = db.task(task["task_id"])
    task = db.transition(
        task["task_id"],
        "tdd",
        expected_revision=task["revision"],
        owner_epoch=second["owner_epoch"],
    )
    assert task["phase"] == "tdd"


def test_active_lease_cannot_be_stolen_by_another_owner(tmp_path):
    db = HarnessDatabase(tmp_path)
    _start(db)
    db.acquire_lease("scope-a", "owner-a", ttl_seconds=10, now=100)

    with pytest.raises(StateTransitionError, match="active lease"):
        db.acquire_lease("scope-a", "owner-b", ttl_seconds=10, now=105)
