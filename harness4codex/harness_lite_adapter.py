from __future__ import annotations

import json
import os
import re
import subprocess
from collections.abc import Callable, Iterable, Mapping
from dataclasses import dataclass
from hashlib import sha256
from pathlib import Path
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import urlsplit
from urllib.request import Request, urlopen

"""Harness4Codex adapter for the current Harness Lite control contract.

Harness4Codex remains the supervisor. This module translates its C-levels to
TaskEnvelopeV1, performs advisory route previews, and exposes submission only
through the explicitly gated CLI.
"""


def _digest(value: str) -> str:
    return "sha256:" + sha256(value.encode("utf-8")).hexdigest()


def _canonical(value: object) -> str:
    if value is None:
        return "null"
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, (int, float)):
        return repr(value)
    if isinstance(value, str):
        return json.dumps(value, ensure_ascii=False, separators=(",", ":"))
    if isinstance(value, (list, tuple)):
        return "[" + ",".join(_canonical(item) for item in value) + "]"
    if isinstance(value, dict):
        pairs = sorted(((key, inner) for key, inner in value.items() if inner is not None), key=lambda item: item[0])
        return "{" + ",".join(_canonical(key) + ":" + _canonical(inner) for key, inner in pairs) + "}"
    raise TypeError(f"cannot canonicalise {type(value).__name__}")


@dataclass(frozen=True)
class LiteCallResult:
    ok: bool
    status: int
    result: dict[str, Any] | None = None
    code: str | None = None
    message: str | None = None


LiteOpener = Callable[..., Any]


class HarnessLiteClient:
    """Authenticated, standard-library client for the loopback control plane."""

    def __init__(
        self,
        base_url: str,
        token: str,
        *,
        timeout: float = 1.5,
        opener: LiteOpener = urlopen,
    ):
        parsed = urlsplit(base_url)
        if parsed.scheme not in {"http", "https"} or parsed.hostname not in {"127.0.0.1", "localhost", "::1"}:
            raise ValueError("Harness Lite control URL must use a loopback HTTP origin")
        if parsed.username or parsed.password or parsed.query or parsed.fragment or parsed.path not in {"", "/"}:
            raise ValueError("Harness Lite control URL must be a loopback origin without credentials or path")
        self.base_url = base_url.rstrip("/")
        self._token = token
        self.timeout = min(max(timeout, 0.1), 2.0)
        self._opener = opener

    @classmethod
    def from_env(cls, env: Mapping[str, str] | None = None) -> HarnessLiteClient | None:
        source = os.environ if env is None else env
        token = source.get("HARNESS_CONTROL_TOKEN", "")
        if not token:
            return None
        return cls(source.get("HARNESS_CONTROL_URL", "http://127.0.0.1:8787"), token)

    def preview(self, envelope: dict[str, Any]) -> LiteCallResult:
        return self._post("/control/v1/routes/preview", envelope)

    def submit(self, envelope: dict[str, Any]) -> LiteCallResult:
        return self._post("/control/v1/tasks", envelope)

    def _post(self, path: str, body: dict[str, Any]) -> LiteCallResult:
        request = Request(
            self.base_url + path,
            data=json.dumps(body, ensure_ascii=False, separators=(",", ":")).encode("utf-8"),
            headers={
                "Authorization": f"Bearer {self._token}",
                "Accept": "application/json",
                "Content-Type": "application/json",
            },
            method="POST",
        )
        try:
            with self._opener(request, timeout=self.timeout) as response:
                status = int(getattr(response, "status", 200))
                payload = json.loads(response.read().decode("utf-8"))
        except HTTPError as exc:
            return LiteCallResult(False, exc.code, code="HTTP_ERROR", message=str(exc))
        except (URLError, OSError, TimeoutError) as exc:
            return LiteCallResult(False, 0, code="CAPABILITY_UNAVAILABLE", message=str(exc))
        except (UnicodeDecodeError, json.JSONDecodeError, TypeError, ValueError) as exc:
            return LiteCallResult(False, 0, code="INVALID_RESPONSE", message=str(exc))
        if not isinstance(payload, dict):
            return LiteCallResult(False, status, code="INVALID_RESPONSE", message="response is not an object")
        if payload.get("ok") is True:
            result = payload.get("result")
            return LiteCallResult(True, status, result=result if isinstance(result, dict) else {})
        return LiteCallResult(
            False,
            status,
            code=str(payload.get("code") or "CONTROL_ERROR"),
            message=str(payload.get("message") or ""),
        )


def reaches_the_plane(level: str) -> bool:
    return level != "C0"


def lite_route_for(level: str) -> tuple[str, str, str, str]:
    """Return Lite level, risk, task kind, and mutation mode."""
    routes = {
        "C0": ("L0", "R0", "diagnose", "read-only"),
        "C1": ("L1", "R1", "diagnose", "isolated-worktree"),
        "C2": ("L2", "R2", "implement", "isolated-worktree"),
        "C3": ("L2", "R3", "implement", "isolated-worktree"),
        "CR": ("L1", "R1", "review", "read-only"),
        "DOCS": ("L1", "R0", "verify", "read-only"),
    }
    try:
        return routes[level]
    except KeyError as exc:
        raise ValueError(f"unsupported Harness4Codex level: {level}") from exc


def build_task_envelope(
    *,
    level: str,
    objective: str,
    workspace_path: str,
    base_revision: str,
    session_id: str,
    acceptance_criteria: Iterable[str] | None = None,
    allowed_commands: Iterable[str] = (),
    requested_profile: str = "auto",
    data_class: str = "internal",
    max_cost_usd: float = 0.0,
    max_runtime_sec: int = 300,
) -> dict[str, Any]:
    if not objective.strip():
        raise ValueError("objective must not be empty")
    if not re.fullmatch(r"[0-9a-f]{40}", base_revision):
        raise ValueError("base_revision must be a 40-character lowercase git object id")
    _lite_level, risk, kind, mutation = lite_route_for(level)
    criteria = list(acceptance_criteria or ["Satisfazer o pedido e apresentar evidência verificável."])
    workspace = str(Path(workspace_path).resolve())
    identity = _canonical(
        {
            "schemaVersion": "1",
            "level": level,
            "objective": objective,
            "workspace": workspace,
            "baseRevision": base_revision,
            "sessionId": session_id,
        }
    )
    return {
        "schemaVersion": "1",
        "kind": kind,
        "objective": objective,
        "workspace": {"path": workspace, "baseRevision": base_revision},
        "inputs": [],
        "acceptance": {
            "criteria": [{"id": f"AC-{index}", "text": text} for index, text in enumerate(criteria, 1)],
            "allowedCommands": list(allowed_commands),
        },
        "execution": {
            "mutation": mutation,
            "dataClass": data_class,
            "requestedProfile": requested_profile,
            "riskHint": risk,
            "maxCostUsd": float(max_cost_usd),
            "maxRuntimeSec": int(max_runtime_sec),
            "allowedWriteGlobs": ["**"] if mutation == "isolated-worktree" else [],
        },
        "provenance": {"idempotencyKey": _digest(identity)},
    }


def execution_is_enabled(env: Mapping[str, str] | None = None) -> bool:
    source = os.environ if env is None else env
    enabled = source.get("HARNESS4CODEX_LITE_EXECUTE", "").strip().lower() in {"1", "true", "yes", "on"}
    try:
        budget = float(source.get("HARNESS4CODEX_LITE_MAX_COST_USD", "0"))
    except ValueError:
        return False
    return enabled and budget > 0


def evidence_bundle_is_acceptable(bundle: Mapping[str, Any]) -> bool:
    if bundle.get("status") != "succeeded":
        return False
    artifacts = bundle.get("artifacts")
    acceptance = bundle.get("acceptance")
    if not isinstance(artifacts, list) or not artifacts:
        return False
    if not isinstance(acceptance, list) or not acceptance:
        return False
    for criterion in acceptance:
        if not isinstance(criterion, dict) or criterion.get("outcome") != "pass":
            return False
        evidence = criterion.get("evidence")
        if not isinstance(evidence, list) or not evidence:
            return False
    return True


def git_base_revision(workspace_path: str | Path) -> str | None:
    try:
        completed = subprocess.run(
            ["git", "-C", str(workspace_path), "rev-parse", "HEAD"],
            check=False,
            capture_output=True,
            text=True,
            timeout=1.0,
        )
    except (OSError, subprocess.TimeoutExpired):
        return None
    revision = completed.stdout.strip().lower()
    return revision if completed.returncode == 0 and re.fullmatch(r"[0-9a-f]{40}", revision) else None


def preview_for_prompt(
    *,
    level: str,
    objective: str,
    workspace_path: str | Path,
    session_id: str,
    env: Mapping[str, str] | None = None,
) -> LiteCallResult | None:
    if not reaches_the_plane(level):
        return None
    client = HarnessLiteClient.from_env(env)
    if client is None:
        return None
    revision = git_base_revision(workspace_path)
    if revision is None:
        return LiteCallResult(False, 0, code="NOT_GIT_WORKSPACE", message="workspace has no Git revision")
    source = os.environ if env is None else env
    try:
        preview_budget = float(source.get("HARNESS4CODEX_LITE_PREVIEW_MAX_COST_USD", "0"))
    except ValueError:
        preview_budget = 0.0
    envelope = build_task_envelope(
        level=level,
        objective=objective,
        workspace_path=str(workspace_path),
        base_revision=revision,
        session_id=session_id,
        max_cost_usd=max(preview_budget, 0.0),
    )
    return client.preview(envelope)


def project_fingerprint_for(paths: Iterable[str]) -> str:
    return _digest("\n".join(sorted(paths)))
