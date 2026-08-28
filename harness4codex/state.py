from __future__ import annotations

import hashlib
import json
import os
import time
import uuid
from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import asdict
from datetime import datetime, timezone
from pathlib import Path

from .classifier import BUG_PIPELINE, Classification
from .contract import ContractSnapshot
from .state_db import HarnessDatabase, StateTransitionError


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
        "tier": "L0",
        "kind": "idle",
        "status": "idle",
        "pipeline": [],
        "current_step": None,
        "revision": 0,
        "code_revision": 0,
        "owner_epoch": 1,
        "pending_gate": None,
        "prompt": None,
        "files": [],
        "verified": False,
        "last_verification": None,
        "stop_continuations": 0,
        "started_at": None,
        "updated_at": now,
    }


class HarnessStateStore:
    def __init__(
        self,
        home: str | os.PathLike[str] | None = None,
        scope: str | None = None,
        memory_home: str | os.PathLike[str] | None = None,
    ):
        self.home = Path(home) if home is not None else default_harness_home()
        self.scope = scope
        self.memory_home = Path(memory_home) if memory_home is not None else self.home
        self.state_path = self.home / "state.json"
        self.events_path = self.home / "events.jsonl"
        self.errors_path = self.home / "errors.log"
        self.lock_path = self.home / "state.json.lock"
        self.home.mkdir(parents=True, exist_ok=True)
        self.database = HarnessDatabase(self.memory_home)
        self.contract = ContractSnapshot.load()

    @contextmanager
    def _lock(self, timeout: float = 2.0) -> Iterator[None]:
        deadline = time.monotonic() + timeout
        owner_token = f"{os.getpid()} {uuid.uuid4().hex} {time.time():.6f}"
        while True:
            try:
                descriptor = os.open(self.lock_path, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
                try:
                    os.write(descriptor, (owner_token + "\n").encode("utf-8"))
                finally:
                    os.close(descriptor)
                break
            except PermissionError as exc:
                if time.monotonic() >= deadline:
                    raise HarnessStateError(f"Timed out waiting for state lock: {self.lock_path}") from exc
                time.sleep(0.01)
                continue
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
            if self.lock_path.is_dir():
                for child in self.lock_path.iterdir():
                    child.unlink(missing_ok=True)
                self.lock_path.rmdir()
            else:
                self.lock_path.unlink(missing_ok=True)
        except OSError:
            pass

    def _release_lock(self, owner_token: str) -> None:
        try:
            if not self.lock_path.is_file():
                return
            current_owner = self.lock_path.read_text(encoding="utf-8").strip()
            if current_owner and current_owner != owner_token:
                return
            self.lock_path.unlink(missing_ok=True)
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
            normalized = self.contract.normalize(classification.level, classification.kind)
            state = default_state()
            state.update(
                {
                    "task_id": f"{int(time.time() * 1000)}-{classification.level.lower()}",
                    "classification": asdict(classification),
                    "level": classification.level,
                    "tier": normalized["tier"],
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
            transactional = self.database.start_task(
                scope_id=self.scope or "legacy",
                legacy_level=classification.level,
                tier=normalized["tier"],
                kind=normalized["kind"],
                pipeline=classification.pipeline.copy(),
                prompt=prompt,
                task_id=state["task_id"],
            )
            self._merge_transactional(state, transactional)
            return self._write_unlocked(state)

    def record_file(self, path: str) -> dict:
        normalized_path = str(Path(path))
        with self._lock():
            state = self._read_unlocked()
            files = state.setdefault("files", [])
            if normalized_path not in files:
                files.append(normalized_path)
            if state.get("verified"):
                state["verified"] = False
                state["last_verification"] = None
                if state.get("pipeline"):
                    state["status"] = "active"
            transactional = (
                self.database.touch_file(state["task_id"], normalized_path)
                if state.get("task_id")
                else None
            )
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
                normalized_classification = self.contract.normalize("C1", "bug")
                transactional = self.database.reclassify(
                    state["task_id"],
                    legacy_level="C1",
                    tier=normalized_classification["tier"],
                    kind=normalized_classification["kind"],
                    pipeline=state["pipeline"],
                )
            if transactional is not None:
                self._merge_transactional(state, transactional)
            return self._write_unlocked(state)

    def mark_verified(self, command: str) -> dict:
        return self.record_verification(
            command,
            exit_code=0,
            tests_collected=1,
            tests_passed=1,
            output_hash=hashlib.sha256(command.encode("utf-8")).hexdigest(),
        )

    def record_verification(
        self,
        command: str,
        *,
        exit_code: int | None,
        tests_collected: int | None,
        tests_passed: int | None,
        output_hash: str | None,
    ) -> dict:
        with self._lock():
            state = self._read_unlocked()
            valid = exit_code == 0 and bool(tests_collected and tests_collected > 0) and tests_passed == tests_collected
            state["verified"] = valid
            state["last_verification"] = {
                "command": command,
                "at": utc_now(),
                "exit_code": exit_code,
                "tests_collected": tests_collected,
                "tests_passed": tests_passed,
                "output_hash": output_hash,
            }
            if valid and state.get("status") == "active":
                state["status"] = "verified"
            if state.get("task_id"):
                transactional = self.database.record_evidence(
                    state["task_id"],
                    evidence_type="test",
                    command=command,
                    exit_code=exit_code,
                    tests_collected=tests_collected,
                    tests_passed=tests_passed,
                    output_hash=output_hash,
                )
                self._merge_transactional(state, transactional)
            return self._write_unlocked(state)

    def increment_stop_continuations(self) -> dict:
        with self._lock():
            state = self._read_unlocked()
            state["stop_continuations"] = int(state.get("stop_continuations") or 0) + 1
            return self._write_unlocked(state)

    def set_pending_gate(self, gate_type: str) -> dict:
        with self._lock():
            state = self._read_unlocked()
            state["status"] = "awaiting_gate"
            state["pending_gate"] = gate_type
            if state.get("task_id"):
                transactional = self.database.open_gate(state["task_id"], gate_type)
                self._merge_transactional(state, transactional)
            return self._write_unlocked(state)

    def log_event(self, event: str, payload: dict) -> None:
        record = {"at": utc_now(), "event": event, "payload": payload}
        with self._lock():
            state = self._read_unlocked()
            with self.events_path.open("a", encoding="utf-8") as handle:
                handle.write(json.dumps(record, sort_keys=True) + "\n")
            self.database.log_event(
                self.scope or "legacy",
                event,
                payload,
                task_id=state.get("task_id"),
            )

    def log_error(self, message: str) -> None:
        line = f"{utc_now()} {message}\n"
        try:
            with self.errors_path.open("a", encoding="utf-8") as handle:
                handle.write(line)
        except OSError:
            # Error reporting is a last-resort path and must not recursively
            # fail the hook whose original exception it was meant to preserve.
            pass

    @staticmethod
    def _merge_transactional(state: dict, transactional: dict) -> None:
        state["tier"] = transactional["tier"]
        state["kind"] = transactional["kind"]
        state["current_step"] = transactional["phase"]
        state["revision"] = transactional["revision"]
        state["code_revision"] = transactional["code_revision"]
        state["owner_epoch"] = transactional["owner_epoch"]
        state["pending_gate"] = transactional["pending_gate"]
        state["verified"] = transactional["verified"]
        state["status"] = transactional["status"]


def store_for_payload(payload: dict, home: str | os.PathLike[str] | None = None) -> HarnessStateStore:
    base_home = Path(home) if home is not None else default_harness_home()
    session_id = payload.get("session_id") or payload.get("sessionId")
    if not session_id:
        return HarnessStateStore(base_home)
    cwd = payload.get("cwd") or payload.get("working_directory") or payload.get("workingDirectory") or ""
    scope = state_scope_key(str(session_id), str(cwd))
    return HarnessStateStore(base_home / "sessions" / scope, scope=scope, memory_home=base_home)


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
