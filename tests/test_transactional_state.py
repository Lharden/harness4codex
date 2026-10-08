from __future__ import annotations

from datetime import datetime

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


def test_starting_new_task_cancels_pending_gates_on_abandoned_task(tmp_path):
    db = HarnessDatabase(tmp_path)
    first = db.open_gate(_start(db)["task_id"], "escalation")

    _start(db)

    abandoned = db.task(first["task_id"])
    assert abandoned["status"] == "abandoned"
    assert abandoned["pending_gate"] is None


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


def test_latest_failing_test_revokes_passing_evidence_for_same_revision(tmp_path):
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
        output_hash="passing",
    )

    task = db.record_evidence(
        task["task_id"],
        evidence_type="test",
        command="pytest -q",
        exit_code=1,
        tests_collected=4,
        tests_passed=3,
        output_hash="failing",
    )

    assert task["verified"] is False
    assert task["status"] == "active"
    with pytest.raises(StateTransitionError, match="fresh verification"):
        db.complete(task["task_id"], expected_revision=task["revision"])


def test_non_test_evidence_does_not_revoke_latest_passing_test(tmp_path):
    db = HarnessDatabase(tmp_path)
    task = _start(db, level="C1", kind="bug")
    task = db.record_evidence(
        task["task_id"],
        evidence_type="test",
        command="pytest -q",
        exit_code=0,
        tests_collected=2,
        tests_passed=2,
        output_hash="passing",
    )

    task = db.record_evidence(
        task["task_id"],
        evidence_type="review",
        command=None,
        exit_code=None,
        tests_collected=None,
        tests_passed=None,
        output_hash="review",
    )

    assert task["verified"] is True


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


def _expirar(db, scope, **kwargs):
    return db.expire_stale_tasks(scope, **kwargs)


def test_stale_task_ttl_abandons_pipeline_and_releases_scope(tmp_path):
    db = HarnessDatabase(tmp_path)
    task = _start(db)
    started = datetime.fromisoformat(task["started_at"]).timestamp()

    assert _expirar(db, "scope-a", ttl_seconds=3600, now=started + 3599) == []

    expired = _expirar(db, "scope-a", ttl_seconds=3600, now=started + 3601)

    assert [t["task_id"] for t in expired] == [task["task_id"]]
    assert expired[0]["status"] == "abandoned"
    assert db.current_task("scope-a") is None


def test_stale_task_ttl_cancels_a_pending_human_gate(tmp_path):
    db = HarnessDatabase(tmp_path)
    task = db.open_gate(_start(db)["task_id"], "escalation")
    started = datetime.fromisoformat(task["started_at"]).timestamp()

    expired = _expirar(db, "scope-a", ttl_seconds=1, now=started + 2)

    assert [t["status"] for t in expired] == ["abandoned"]
    assert expired[0]["pending_gate"] is None


def test_ttl_does_not_expire_a_fresh_replacement_task(tmp_path):
    db = HarnessDatabase(tmp_path)
    _start(db)
    replacement = _start(db)
    started = datetime.fromisoformat(replacement["started_at"]).timestamp()

    expired = _expirar(db, "scope-a", ttl_seconds=3600, now=started + 60)

    assert expired == []
    assert db.current_task("scope-a")["task_id"] == replacement["task_id"]


def test_expiry_records_each_expired_task_as_event(tmp_path):
    db = HarnessDatabase(tmp_path)
    task = _start(db)
    started = datetime.fromisoformat(task["started_at"]).timestamp()

    _expirar(db, "scope-a", ttl_seconds=1, now=started + 2)

    with db._connect() as connection:
        events = connection.execute(
            "SELECT task_id, scope_id FROM events WHERE event_type = 'pipeline-expired'"
        ).fetchall()
    assert [(row["task_id"], row["scope_id"]) for row in events] == [(task["task_id"], "scope-a")]


def test_expiry_without_scope_sweeps_every_scope_and_records_each(tmp_path):
    db = HarnessDatabase(tmp_path)
    a = _start(db, scope="scope-a")
    b = _start(db, scope="scope-b")
    started = datetime.fromisoformat(b["started_at"]).timestamp()

    expired = db.expire_stale_tasks(None, ttl_seconds=1, now=started + 2)

    assert {t["task_id"] for t in expired} == {a["task_id"], b["task_id"]}
    assert db.current_task("scope-a") is None
    assert db.current_task("scope-b") is None
    with db._connect() as connection:
        recorded = {
            row["task_id"]
            for row in connection.execute("SELECT task_id FROM events WHERE event_type = 'pipeline-expired'")
        }
    assert recorded == {a["task_id"], b["task_id"]}


def test_expiry_with_scope_leaves_other_scopes_alone(tmp_path):
    db = HarnessDatabase(tmp_path)
    _start(db, scope="scope-a")
    other = _start(db, scope="scope-b")
    started = datetime.fromisoformat(other["started_at"]).timestamp()

    expired = db.expire_stale_tasks("scope-a", ttl_seconds=1, now=started + 2)

    assert len(expired) == 1
    assert db.task(other["task_id"])["status"] == "active"


def test_escalation_gate_approval_returns_the_task_to_active_in_the_same_phase(tmp_path):
    db = HarnessDatabase(tmp_path)
    task = db.open_gate(_start(db)["task_id"], "escalation")
    phase = task["phase"]

    resolved = db.resolve_gate(task["task_id"], "escalation", "approve", expected_revision=task["revision"])

    assert resolved["status"] == "active"
    assert resolved["pending_gate"] is None
    assert resolved["phase"] == phase


def test_gate_rejection_abandons_the_task_and_closes_the_gate(tmp_path):
    db = HarnessDatabase(tmp_path)
    task = db.open_gate(_start(db)["task_id"], "escalation")

    rejected = db.resolve_gate(task["task_id"], "escalation", "reject", expected_revision=task["revision"])

    assert rejected["status"] == "abandoned"
    assert rejected["pending_gate"] is None
    assert db.current_task("scope-a") is None
    with db._connect() as connection:
        gate = connection.execute("SELECT status, decision FROM gates WHERE task_id = ?", (task["task_id"],)).fetchone()
    assert (gate["status"], gate["decision"]) == ("resolved", "reject")


def test_gate_resolution_rejects_unknown_decision_and_stale_revision(tmp_path):
    db = HarnessDatabase(tmp_path)
    task = db.open_gate(_start(db)["task_id"], "escalation")

    with pytest.raises(StateTransitionError):
        db.resolve_gate(task["task_id"], "escalation", "maybe", expected_revision=task["revision"])
    with pytest.raises(StateTransitionError):
        db.resolve_gate(task["task_id"], "escalation", "reject", expected_revision=task["revision"] - 1)
    assert db.task(task["task_id"])["status"] == "awaiting_gate"
