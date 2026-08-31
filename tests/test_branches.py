from pathlib import Path
import sqlite3

import pytest

from harness4codex.branches import BranchKeeper, BranchPolicyError
from harness4codex.state_db import HarnessDatabase, StateTransitionError


def _task(db: HarnessDatabase):
    return db.start_task(
        scope_id="session|repo|worktree",
        legacy_level="C2",
        tier="L2",
        kind="feature",
        pipeline=["discuss", "tdd"],
        prompt="build branch keeper",
    )


def test_branch_offer_requires_approval_before_open_and_is_recallable(tmp_path: Path):
    db = HarnessDatabase(tmp_path)
    task = _task(db)
    keeper = BranchKeeper(db)
    branch = keeper.offer(task["task_id"], "Graph Retrieval", "independent retrieval work", turn=10)

    seed = tmp_path / "seed.md"
    seed.write_text("Investigate graph retrieval", encoding="utf-8")
    with pytest.raises(BranchPolicyError, match="approval"):
        keeper.open(branch["branch_id"], seed_path=seed)

    keeper.approve(branch["branch_id"])
    opened = keeper.open(branch["branch_id"], seed_path=seed)
    recalled = keeper.recall(branch["branch_id"])

    assert opened["status"] == "open"
    assert opened["launch_argv"] == ["codex", "fork", "--last", "Investigate graph retrieval"]
    assert recalled["status"] == "recalled"


def test_branch_limits_and_topic_deduplication(tmp_path: Path):
    db = HarnessDatabase(tmp_path)
    task = _task(db)
    keeper = BranchKeeper(db, max_offers=2, cooldown_turns=8)
    keeper.offer(task["task_id"], "Alpha topic", "first", turn=10)
    with pytest.raises(BranchPolicyError, match="cooldown"):
        keeper.offer(task["task_id"], "Beta topic", "second", turn=12)
    with pytest.raises(BranchPolicyError, match="already exists"):
        keeper.offer(task["task_id"], "Alpha topic", "duplicate", turn=20)


def test_close_records_conclusion(tmp_path: Path):
    db = HarnessDatabase(tmp_path)
    task = _task(db)
    keeper = BranchKeeper(db)
    branch = keeper.offer(task["task_id"], "Audit trail", "separate audit", turn=10)
    keeper.approve(branch["branch_id"])
    seed = tmp_path / "audit.md"
    seed.write_text("Audit the state schema", encoding="utf-8")
    keeper.open(branch["branch_id"], seed_path=seed)

    closed = keeper.close(branch["branch_id"], "Audit schema agreed")

    assert closed["status"] == "closed"
    assert closed["conclusion"] == "Audit schema agreed"


def test_branch_can_fork_an_explicit_codex_session(tmp_path: Path):
    db = HarnessDatabase(tmp_path)
    task = _task(db)
    keeper = BranchKeeper(db)
    branch = keeper.offer(task["task_id"], "Explicit session", "fork exact session", turn=10)
    keeper.approve(branch["branch_id"])
    seed = tmp_path / "session-seed.md"
    seed.write_text("Continue this branch", encoding="utf-8")

    opened = keeper.open(branch["branch_id"], seed_path=seed, session_id="session-123")

    assert opened["launch_argv"] == ["codex", "fork", "session-123", "Continue this branch"]


def test_each_branch_approval_resolves_only_its_own_gate(tmp_path: Path):
    db = HarnessDatabase(tmp_path)
    task = _task(db)
    keeper = BranchKeeper(db, max_offers=3, cooldown_turns=0)
    first = keeper.offer(task["task_id"], "First branch", "first independent topic", turn=10)
    second = keeper.offer(task["task_id"], "Second branch", "second unrelated lane", turn=11)

    keeper.approve(first["branch_id"])

    with sqlite3.connect(tmp_path / "harness.db") as connection:
        rows = connection.execute(
            "SELECT subject_id, status FROM gates WHERE task_id = ? AND gate_type = 'branch-open'",
            (task["task_id"],),
        ).fetchall()
    assert dict(rows) == {first["branch_id"]: "resolved", second["branch_id"]: "pending"}
    assert db.task(task["task_id"])["status"] == "awaiting_gate"
    assert db.task(task["task_id"])["pending_gate"] == f"branch-open:{second['branch_id']}"

    keeper.approve(second["branch_id"])
    assert db.task(task["task_id"])["status"] == "active"


def test_branch_offer_and_open_limits_are_enforced_inside_database_transaction(tmp_path: Path):
    db = HarnessDatabase(tmp_path)
    task = _task(db)
    db.create_branch(
        task["task_id"], branch_id="b-one", slug="one", name="One", topic="one",
        topic_hash="hash-one", offered_turn=10, max_offers=1, cooldown_turns=0,
    )
    with pytest.raises(StateTransitionError, match="offer limit"):
        db.create_branch(
            task["task_id"], branch_id="b-two", slug="two", name="Two", topic="two",
            topic_hash="hash-two", offered_turn=11, max_offers=1, cooldown_turns=0,
        )

    db.approve_branch("b-one")
    db.open_branch("b-one", seed_path="one.md", max_open=1)
    db.create_branch(
        task["task_id"], branch_id="b-three", slug="three", name="Three", topic="three",
        topic_hash="hash-three", offered_turn=20, max_offers=3, cooldown_turns=0,
    )
    db.approve_branch("b-three")
    with pytest.raises(StateTransitionError, match="open branch limit"):
        db.open_branch("b-three", seed_path="three.md", max_open=1)
