from pathlib import Path

import pytest

from harness4codex.branches import BranchKeeper, BranchPolicyError
from harness4codex.state_db import HarnessDatabase


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

    with pytest.raises(BranchPolicyError, match="approval"):
        keeper.open(branch["branch_id"], seed_path="seed.md")

    keeper.approve(branch["branch_id"])
    opened = keeper.open(branch["branch_id"], seed_path="seed.md")
    recalled = keeper.recall(branch["branch_id"])

    assert opened["status"] == "open"
    assert opened["launch_argv"][:2] == ["codex", "fork"]
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
    keeper.open(branch["branch_id"], seed_path="audit.md")

    closed = keeper.close(branch["branch_id"], "Audit schema agreed")

    assert closed["status"] == "closed"
    assert closed["conclusion"] == "Audit schema agreed"
