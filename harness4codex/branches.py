from __future__ import annotations

import hashlib
import re
import sqlite3
import uuid
from pathlib import Path
from typing import Any

from .state_db import HarnessDatabase, StateTransitionError


class BranchPolicyError(ValueError):
    pass


class BranchKeeper:
    def __init__(
        self,
        database: HarnessDatabase,
        *,
        max_open: int = 3,
        max_offers: int = 2,
        cooldown_turns: int = 8,
        similarity_threshold: float = 0.60,
    ):
        self.database = database
        self.max_open = max_open
        self.max_offers = max_offers
        self.cooldown_turns = cooldown_turns
        self.similarity_threshold = similarity_threshold

    def offer(self, task_id: str, name: str, topic: str, *, turn: int) -> dict[str, Any]:
        existing = self.database.list_branches(task_id)
        candidate_slug = _slug(name)
        if len(existing) >= self.max_offers:
            raise BranchPolicyError("branch offer limit reached")
        if existing and turn - max(int(branch["offered_turn"]) for branch in existing) < self.cooldown_turns:
            raise BranchPolicyError("branch offer cooldown is active")
        for branch in existing:
            if branch["slug"] == candidate_slug or _jaccard(topic, str(branch["topic"])) >= self.similarity_threshold:
                raise BranchPolicyError("branch topic already exists")
        branch_id = f"b-{uuid.uuid4().hex[:12]}"
        topic_hash = hashlib.sha256(_normalize(topic).encode("utf-8")).hexdigest()
        try:
            return self.database.create_branch(
                task_id,
                branch_id=branch_id,
                slug=candidate_slug,
                name=name.strip(),
                topic=topic.strip(),
                topic_hash=topic_hash,
                offered_turn=turn,
                max_offers=self.max_offers,
                cooldown_turns=self.cooldown_turns,
            )
        except (StateTransitionError, sqlite3.IntegrityError) as exc:
            raise BranchPolicyError(str(exc)) from exc

    def approve(self, branch_id: str) -> dict[str, Any]:
        try:
            return self.database.approve_branch(branch_id)
        except StateTransitionError as exc:
            raise BranchPolicyError(str(exc)) from exc

    def open(
        self,
        branch_id: str,
        *,
        seed_path: str | Path,
        session_id: str | None = None,
    ) -> dict[str, Any]:
        branch = self.database.branch(branch_id)
        if not branch.get("approved_at"):
            raise BranchPolicyError("branch-open approval is required")
        seed = Path(seed_path)
        try:
            prompt = seed.read_text(encoding="utf-8").strip()
        except OSError as exc:
            raise BranchPolicyError(f"branch seed could not be read: {seed}") from exc
        if not prompt:
            raise BranchPolicyError("branch seed is empty")
        try:
            updated = self.database.open_branch(
                branch_id,
                seed_path=str(seed),
                max_open=self.max_open,
            )
        except StateTransitionError as exc:
            raise BranchPolicyError(str(exc)) from exc
        fork_target = session_id.strip() if session_id and session_id.strip() else "--last"
        updated["launch_argv"] = ["codex", "fork", fork_target, prompt]
        return updated

    def recall(self, branch_id: str) -> dict[str, Any]:
        return self.database.update_branch(branch_id, status="recalled")

    def close(self, branch_id: str, conclusion: str) -> dict[str, Any]:
        if not conclusion.strip():
            raise BranchPolicyError("branch conclusion is required")
        return self.database.update_branch(branch_id, status="closed", conclusion=conclusion.strip())

    def list(self, task_id: str) -> list[dict[str, Any]]:
        return self.database.list_branches(task_id)


def _normalize(text: str) -> str:
    return " ".join(re.findall(r"[a-z0-9]+", text.casefold()))


def _jaccard(left: str, right: str) -> float:
    a, b = set(_normalize(left).split()), set(_normalize(right).split())
    if not a and not b:
        return 1.0
    return len(a & b) / max(len(a | b), 1)


def _slug(value: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", value.casefold()).strip("-")
    return slug or "branch"
