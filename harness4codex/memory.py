from __future__ import annotations

from dataclasses import dataclass, field
import json
from pathlib import Path
import sqlite3
from typing import Any

from .state import default_harness_home, utc_now


@dataclass(frozen=True)
class ConsolidationReport:
    events_read: int
    proposals: list[dict[str, str]] = field(default_factory=list)
    summary: str = ""


class HarnessMemoryStore:
    def __init__(self, home: str | Path | None = None):
        self.home = Path(home) if home is not None else default_harness_home()
        self.home.mkdir(parents=True, exist_ok=True)
        self.db_path = self.home / "memory.sqlite3"
        self._ensure_schema()

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.db_path)
        connection.row_factory = sqlite3.Row
        return connection

    def _ensure_schema(self) -> None:
        with self._connect() as connection:
            connection.executescript(
                """
                CREATE TABLE IF NOT EXISTS history (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    event TEXT NOT NULL,
                    text TEXT NOT NULL,
                    metadata_json TEXT NOT NULL,
                    created_at TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS memories (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    scope TEXT NOT NULL,
                    kind TEXT NOT NULL,
                    key TEXT NOT NULL,
                    value TEXT NOT NULL,
                    source TEXT NOT NULL,
                    confidence REAL NOT NULL DEFAULT 1.0,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    UNIQUE(scope, kind, key)
                );
                """
            )

    def record_history(self, event: str, text: str, metadata: dict[str, Any] | None = None) -> None:
        with self._connect() as connection:
            connection.execute(
                "INSERT INTO history(event, text, metadata_json, created_at) VALUES (?, ?, ?, ?)",
                (event, text, json.dumps(metadata or {}, sort_keys=True), utc_now()),
            )

    def remember(
        self,
        scope: str,
        kind: str,
        key: str,
        value: str,
        source: str,
        confidence: float = 1.0,
    ) -> None:
        now = utc_now()
        with self._connect() as connection:
            connection.execute(
                """
                INSERT INTO memories(scope, kind, key, value, source, confidence, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(scope, kind, key) DO UPDATE SET
                    value = excluded.value,
                    source = excluded.source,
                    confidence = excluded.confidence,
                    updated_at = excluded.updated_at
                """,
                (scope, kind, key, value, source, confidence, now, now),
            )

    def search(self, query: str, limit: int = 10) -> list[dict[str, Any]]:
        like = f"%{query}%"
        with self._connect() as connection:
            rows = connection.execute(
                """
                SELECT id, event, text, metadata_json, created_at
                FROM history
                WHERE text LIKE ? OR event LIKE ? OR metadata_json LIKE ?
                ORDER BY id DESC
                LIMIT ?
                """,
                (like, like, like, limit),
            ).fetchall()
        return [
            {
                "id": row["id"],
                "event": row["event"],
                "text": row["text"],
                "metadata": json.loads(row["metadata_json"]),
                "created_at": row["created_at"],
            }
            for row in rows
        ]

    def list_memories(
        self,
        scope: str | None = None,
        kind: str | None = None,
        limit: int = 50,
    ) -> list[dict[str, Any]]:
        clauses: list[str] = []
        params: list[Any] = []
        if scope is not None:
            clauses.append("scope = ?")
            params.append(scope)
        if kind is not None:
            clauses.append("kind = ?")
            params.append(kind)
        where = "WHERE " + " AND ".join(clauses) if clauses else ""
        params.append(limit)
        with self._connect() as connection:
            rows = connection.execute(
                f"""
                SELECT scope, kind, key, value, source, confidence, created_at, updated_at
                FROM memories
                {where}
                ORDER BY updated_at DESC, id DESC
                LIMIT ?
                """,
                params,
            ).fetchall()
        return [dict(row) for row in rows]

    def history_count(self) -> int:
        with self._connect() as connection:
            row = connection.execute("SELECT COUNT(*) AS total FROM history").fetchone()
        return int(row["total"])


class MemoryConsolidator:
    def __init__(self, home: str | Path | None = None):
        self.home = Path(home) if home is not None else default_harness_home()
        self.events_path = self.home / "events.jsonl"
        self.store = HarnessMemoryStore(self.home)

    def consolidate(self) -> ConsolidationReport:
        events = self._read_events()
        proposals = self._build_proposals(events)
        for proposal in proposals:
            self.store.remember(
                "global",
                "proposal",
                proposal["key"],
                proposal["value"],
                "memory-consolidator",
                confidence=0.8,
            )
        summary = f"consolidated {len(events)} harness events into {len(proposals)} proposals"
        self.store.record_history(
            "MemoryConsolidation",
            summary,
            {"events_read": len(events), "proposal_keys": [proposal["key"] for proposal in proposals]},
        )
        return ConsolidationReport(events_read=len(events), proposals=proposals, summary=summary)

    def _read_events(self) -> list[dict[str, Any]]:
        if not self.events_path.exists():
            return []
        events: list[dict[str, Any]] = []
        for line in self.events_path.read_text(encoding="utf-8").splitlines():
            if not line.strip():
                continue
            try:
                events.append(json.loads(line))
            except json.JSONDecodeError:
                events.append({"event": "InvalidEventLine", "payload": {"raw": line}})
        return events

    def _build_proposals(self, events: list[dict[str, Any]]) -> list[dict[str, str]]:
        proposals: dict[str, str] = {}
        for event in events:
            payload = event.get("payload") or {}
            event_name = str(event.get("event") or "")
            command = str(payload.get("command") or "")
            reason = str(payload.get("reason") or "")
            if "git reset --hard" in command or "git guard" in reason.lower():
                proposals["git-guardrail-review"] = (
                    "Review whether the repo workflow should document safer alternatives to destructive git commands."
                )
            files = payload.get("files") or []
            if isinstance(files, list) and len(files) >= 4:
                proposals["large-edit-workflow-review"] = (
                    "Large edit detected. Consider documenting expected plan/review checkpoints in WORKFLOW.md."
                )
            if event_name == "Stop" and (payload.get("blocked") or "verification" in reason.lower()):
                proposals["workflow-verification-reminder"] = (
                    "Verification gate blocked completion. Consider adding explicit verification commands to WORKFLOW.md."
                )
        return [{"key": key, "value": value} for key, value in sorted(proposals.items())]
