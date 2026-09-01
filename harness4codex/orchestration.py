from __future__ import annotations

import json
import re
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any


@dataclass(frozen=True)
class Issue:
    id: str
    identifier: str
    title: str
    state: str = "Ready"
    description: str | None = None
    labels: list[str] = field(default_factory=list)
    blocked_by: list[dict[str, Any]] = field(default_factory=list)
    url: str | None = None


@dataclass(frozen=True)
class Workspace:
    path: Path
    issue: Issue
    created_now: bool


class WorkspaceManager:
    def __init__(self, root: str | Path):
        self.root = Path(root).resolve()

    def prepare(self, issue: Issue) -> Workspace:
        self.root.mkdir(parents=True, exist_ok=True)
        workspace_key = sanitize_workspace_key(issue.identifier)
        path = (self.root / workspace_key).resolve()
        if path.parent != self.root:
            raise ValueError(f"Workspace escaped root: {path}")
        created_now = not path.exists()
        path.mkdir(parents=True, exist_ok=True)
        metadata_path = path / ".harness4codex-issue.json"
        metadata_path.write_text(
            json.dumps({"issue": asdict(issue), "workspace_key": workspace_key}, indent=2, sort_keys=True),
            encoding="utf-8",
        )
        return Workspace(path=path, issue=issue, created_now=created_now)


@dataclass(frozen=True)
class OrchestrationPolicy:
    active_states: list[str] = field(default_factory=lambda: ["Ready", "Todo", "In Progress"])
    terminal_states: list[str] = field(default_factory=lambda: ["Done", "Canceled", "Cancelled"])
    max_retry_backoff_ms: int = 300_000

    def is_eligible(self, issue: Issue) -> bool:
        if issue.state not in self.active_states:
            return False
        for blocker in issue.blocked_by:
            state = str(blocker.get("state") or "")
            if state and state not in self.terminal_states:
                return False
        return True

    def retry_backoff_ms(self, attempt: int) -> int:
        attempt = max(0, attempt)
        return min(1000 * (2**attempt), self.max_retry_backoff_ms)


def sanitize_workspace_key(identifier: str) -> str:
    value = re.sub(r"[^A-Za-z0-9._-]+", "-", identifier)
    value = value.strip(".-_")
    value = re.sub(r"-{2,}", "-", value)
    return value or "issue"
