from __future__ import annotations

from contextlib import contextmanager
from dataclasses import asdict
from datetime import datetime, timezone
import hashlib
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
        "scope": None,
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
    def __init__(self, home: str | os.PathLike[str] | None = None, scope: str | None = None):
        self.home = Path(home) if home is not None else default_harness_home()
        self.scope = scope
        self.state_path = self.home / "state.json"
        self.events_path = self.home / "events.jsonl"
        self.errors_path = self.home / "errors.log"
        self.lock_path = self.home / "state.json.lockdir"
        self.lock_owner_path = self.lock_path / "owner"
        self.home.mkdir(parents=True, exist_ok=True)

    @contextmanager
    def _lock(self, timeout: float = 2.0) -> Iterator[None]:
        deadline = time.monotonic() + timeout
        owner_token = f"{os.getpid()} {time.time():.6f}"
        while True:
            try:
                self.lock_path.mkdir()
                self.lock_owner_path.write_text(owner_token + "\n", encoding="utf-8")
                break
            except FileExistsError:
                if time.monotonic() >= deadline:
                    raise HarnessStateError(f"Timed out waiting for state lock: {self.lock_path}")
                try:
                    age = time.time() - self.lock_path.stat().st_mtime
                    if age > 30:
                        self._remove_stale_lock()
                        continue
                except OSError:
                    pass
                time.sleep(0.05)
        try:
            yield
        finally:
            self._release_lock(owner_token)

    def _remove_stale_lock(self) -> None:
        try:
            for child in self.lock_path.iterdir():
                child.unlink(missing_ok=True)
            self.lock_path.rmdir()
        except OSError:
            pass

    def _release_lock(self, owner_token: str) -> None:
        try:
            if self.lock_owner_path.exists():
                current_owner = self.lock_owner_path.read_text(encoding="utf-8").strip()
                if current_owner and current_owner != owner_token:
                    return
            self.lock_owner_path.unlink(missing_ok=True)
            self.lock_path.rmdir()
        except OSError:
            pass

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
        state["scope"] = self.scope
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


def store_for_payload(payload: dict, home: str | os.PathLike[str] | None = None) -> HarnessStateStore:
    base_home = Path(home) if home is not None else default_harness_home()
    session_id = payload.get("session_id") or payload.get("sessionId")
    if not session_id:
        return HarnessStateStore(base_home)
    cwd = payload.get("cwd") or payload.get("working_directory") or payload.get("workingDirectory") or ""
    scope = state_scope_key(str(session_id), str(cwd))
    return HarnessStateStore(base_home / "sessions" / scope, scope=scope)


def list_session_states(home: str | os.PathLike[str] | None = None) -> list[dict]:
    base_home = Path(home) if home is not None else default_harness_home()
    sessions_dir = base_home / "sessions"
    if not sessions_dir.exists():
        return []
    states: list[dict] = []
    for state_path in sorted(sessions_dir.glob("*/state.json")):
        try:
            state = json.loads(state_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        state["_state_path"] = str(state_path)
        states.append(state)
    return states


def state_scope_key(session_id: str, cwd: str = "") -> str:
    raw = f"{session_id}\n{Path(cwd).resolve() if cwd else ''}"
    digest = hashlib.sha256(raw.encode("utf-8")).hexdigest()[:16]
    return f"s-{digest}"
