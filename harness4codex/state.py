from __future__ import annotations

from contextlib import contextmanager
from dataclasses import asdict
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import time
from typing import Iterator

from .classifier import BUG_PIPELINE, Classification


class HarnessStateError(RuntimeError):
    pass


def default_harness_home() -> Path:
    configured = os.environ.get("HARNESS4CODEX_HOME")
    if configured:
        return Path(configured).expanduser()
    return Path.home() / ".codex" / "harness"


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def default_state() -> dict:
    now = utc_now()
    return {
        "task_id": None,
        "classification": None,
        "level": "C0",
        "kind": "idle",
        "status": "idle",
        "pipeline": [],
        "current_step": None,
        "prompt": None,
        "files": [],
        "verified": False,
        "last_verification": None,
        "stop_continuations": 0,
        "started_at": None,
        "updated_at": now,
    }


class HarnessStateStore:
    def __init__(self, home: str | os.PathLike[str] | None = None):
        self.home = Path(home) if home is not None else default_harness_home()
        self.state_path = self.home / "state.json"
        self.events_path = self.home / "events.jsonl"
        self.errors_path = self.home / "errors.log"
        self.lock_path = self.home / ".lock"
        self.home.mkdir(parents=True, exist_ok=True)

    @contextmanager
    def _lock(self, timeout: float = 2.0) -> Iterator[None]:
        deadline = time.monotonic() + timeout
        fd: int | None = None
        while True:
            try:
                fd = os.open(self.lock_path, os.O_CREAT | os.O_EXCL | os.O_RDWR)
                break
            except FileExistsError:
                if time.monotonic() >= deadline:
                    raise HarnessStateError(f"Timed out waiting for state lock: {self.lock_path}")
                try:
                    age = time.time() - self.lock_path.stat().st_mtime
                    if age > 30:
                        self.lock_path.unlink(missing_ok=True)
                        continue
                except OSError:
                    pass
                time.sleep(0.05)
        try:
            yield
        finally:
            if fd is not None:
                os.close(fd)
            self.lock_path.unlink(missing_ok=True)

    def _read_unlocked(self) -> dict:
        if not self.state_path.exists():
            state = default_state()
            self._write_unlocked(state)
            return state
        try:
            return json.loads(self.state_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError as exc:
            backup = self.state_path.with_suffix(f".corrupt-{int(time.time())}.json")
            self.state_path.replace(backup)
            state = default_state()
            state["status"] = "idle"
            state["last_error"] = f"Corrupt state moved to {backup}: {exc}"
            self._write_unlocked(state)
            return state

    def _write_unlocked(self, state: dict) -> dict:
        state["updated_at"] = utc_now()
        tmp_path = self.state_path.with_suffix(".tmp")
        tmp_path.write_text(json.dumps(state, indent=2, sort_keys=True), encoding="utf-8")
        os.replace(tmp_path, self.state_path)
        return state

    def load(self) -> dict:
        with self._lock():
            return self._read_unlocked()

    def save(self, state: dict) -> dict:
        with self._lock():
            return self._write_unlocked(state)

    def start_task(self, classification: Classification, prompt: str) -> dict:
        with self._lock():
            now = utc_now()
            state = default_state()
            state.update(
                {
                    "task_id": f"{int(time.time() * 1000)}-{classification.level.lower()}",
                    "classification": asdict(classification),
                    "level": classification.level,
                    "kind": classification.kind,
                    "status": "active" if classification.pipeline else "done",
                    "pipeline": classification.pipeline.copy(),
                    "current_step": classification.pipeline[0] if classification.pipeline else None,
                    "prompt": prompt,
                    "verified": False,
                    "started_at": now,
                    "updated_at": now,
                }
            )
            return self._write_unlocked(state)

    def record_file(self, path: str) -> dict:
        normalized = str(Path(path))
        with self._lock():
            state = self._read_unlocked()
            files = state.setdefault("files", [])
            if normalized not in files:
                files.append(normalized)
            if state.get("level") == "C0" and len(files) >= 3:
                state["level"] = "C1"
                state["kind"] = "escalated-edit"
                state["status"] = "active"
                state["pipeline"] = BUG_PIPELINE.copy()
                state["current_step"] = state["pipeline"][0]
                state["verified"] = False
                state["classification"] = {
                    "level": "C1",
                    "kind": "escalated-edit",
                    "pipeline": BUG_PIPELINE.copy(),
                    "reasons": ["C0 prompt edited three or more files"],
                    "is_task_switch": False,
                }
            return self._write_unlocked(state)

    def mark_verified(self, command: str) -> dict:
        with self._lock():
            state = self._read_unlocked()
            state["verified"] = True
            state["last_verification"] = {"command": command, "at": utc_now()}
            if state.get("status") == "active":
                state["status"] = "verified"
            return self._write_unlocked(state)

    def increment_stop_continuations(self) -> dict:
        with self._lock():
            state = self._read_unlocked()
            state["stop_continuations"] = int(state.get("stop_continuations") or 0) + 1
            return self._write_unlocked(state)

    def log_event(self, event: str, payload: dict) -> None:
        record = {"at": utc_now(), "event": event, "payload": payload}
        with self._lock():
            with self.events_path.open("a", encoding="utf-8") as handle:
                handle.write(json.dumps(record, sort_keys=True) + "\n")

    def log_error(self, message: str) -> None:
        line = f"{utc_now()} {message}\n"
        with self._lock():
            with self.errors_path.open("a", encoding="utf-8") as handle:
                handle.write(line)
