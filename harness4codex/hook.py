from __future__ import annotations

import json
import re
import sys
import traceback
from pathlib import Path
from typing import Any

from .classifier import classify_prompt
from .git_guard import inspect_command
from .state import HarnessStateStore


VERIFICATION_PATTERNS = [
    r"\bpytest\b",
    r"\bnpm\s+(run\s+)?test\b",
    r"\bpnpm\s+(run\s+)?test\b",
    r"\byarn\s+test\b",
    r"\bcargo\s+test\b",
    r"\bgo\s+test\b",
]

PATCH_FILE_PATTERN = re.compile(r"^\*\*\* (?:Add|Update|Delete) File: (.+)$", re.MULTILINE)


def _event_name(payload: dict[str, Any]) -> str:
    return str(payload.get("hook_event_name") or payload.get("hookEventName") or payload.get("event") or "")


def _json(data: dict[str, Any]) -> str:
    return json.dumps(data, ensure_ascii=True, sort_keys=True)


def _context_output(event: str, context: str) -> str:
    return _json({"hookSpecificOutput": {"hookEventName": event, "additionalContext": context}})


def _deny_pretool(event: str, reason: str) -> str:
    return _json(
        {
            "continue": False,
            "stopReason": reason,
            "systemMessage": reason,
            "hookSpecificOutput": {
                "hookEventName": event,
                "permissionDecision": "deny",
                "permissionDecisionReason": reason,
            },
        }
    )


def _deny_permission(reason: str) -> str:
    return _json(
        {
            "continue": False,
            "stopReason": reason,
            "systemMessage": reason,
            "hookSpecificOutput": {
                "hookEventName": "PermissionRequest",
                "permissionDecision": "deny",
                "permissionDecisionReason": reason,
                "decision": {"behavior": "deny", "message": reason},
            },
        }
    )


def _block_stop(reason: str) -> str:
    return _json(
        {
            "continue": False,
            "decision": "block",
            "reason": reason,
            "stopReason": reason,
            "hookSpecificOutput": {"hookEventName": "Stop", "decision": "block", "reason": reason},
        }
    )


def _tool_input(payload: dict[str, Any]) -> dict[str, Any]:
    value = payload.get("tool_input") or payload.get("toolInput") or payload.get("input") or {}
    return value if isinstance(value, dict) else {"command": str(value)}


def _command_from_payload(payload: dict[str, Any]) -> str:
    tool_input = _tool_input(payload)
    command = tool_input.get("command") or tool_input.get("cmd") or tool_input.get("script")
    if command is None:
        return ""
    return str(command)


def _extract_files(payload: dict[str, Any]) -> list[str]:
    tool_input = _tool_input(payload)
    files: list[str] = []
    for key in ("file_path", "path", "target_file"):
        value = tool_input.get(key)
        if value:
            files.append(str(value))
    command = _command_from_payload(payload)
    files.extend(match.strip() for match in PATCH_FILE_PATTERN.findall(command))
    return list(dict.fromkeys(files))


def _looks_like_verification(command: str) -> bool:
    return any(re.search(pattern, command, re.IGNORECASE) for pattern in VERIFICATION_PATTERNS)


def _extract_exit_code(payload: dict[str, Any]) -> int | None:
    for key in ("exit_code", "exitCode", "status"):
        value = payload.get(key)
        if isinstance(value, int):
            return value
    response = payload.get("tool_response") or payload.get("toolResponse") or payload.get("output") or ""
    if isinstance(response, dict):
        for key in ("exit_code", "exitCode", "status"):
            value = response.get(key)
            if isinstance(value, int):
                return value
        response = json.dumps(response)
    match = re.search(r"Exit code:\s*(\d+)", str(response), re.IGNORECASE)
    if match:
        return int(match.group(1))
    return None


def _task_context(state: dict[str, Any], heading: str) -> str:
    pipeline = state.get("pipeline") or []
    return "\n".join(
        [
            "HARNESS4CODEX",
            heading,
            f"Task: {state.get('task_id')}",
            f"Level: {state.get('level')} / {state.get('kind')}",
            f"Skill: codex-harness-workflow",
            f"Pipeline: {', '.join(pipeline) if pipeline else 'none'}",
            "Follow the listed skills in order. Do not claim completion until verification-before-completion has fresh evidence.",
        ]
    )


def _classification_context(state: dict[str, Any]) -> str:
    classification = state.get("classification") or {}
    reasons = classification.get("reasons") or []
    base = _task_context(state, "Classificacao criada para este turno.")
    if reasons:
        base += "\nReasons: " + ", ".join(reasons)
    return base


def _handle_session_start(event: str, store: HarnessStateStore) -> str:
    state = store.load()
    if state.get("status") in {"active", "verified"} and state.get("pipeline"):
        return _context_output(event, _task_context(state, "Retome o pipeline ativo."))
    return ""


def _handle_user_prompt(event: str, payload: dict[str, Any], store: HarnessStateStore) -> str:
    prompt = str(payload.get("prompt") or payload.get("user_prompt") or payload.get("message") or "")
    classification = classify_prompt(prompt)
    current = store.load()
    if current.get("status") == "active" and not classification.is_task_switch:
        store.log_event(event, {"continued": current.get("task_id"), "prompt": prompt})
        return _context_output(event, _task_context(current, "Continue o pipeline ativo."))
    state = store.start_task(classification, prompt)
    store.log_event(event, {"classification": state.get("classification"), "prompt": prompt})
    return _context_output(event, _classification_context(state))


def _handle_pre_tool(event: str, payload: dict[str, Any], store: HarnessStateStore) -> str:
    command = _command_from_payload(payload)
    decision = inspect_command(command)
    store.log_event(event, {"tool": payload.get("tool_name") or payload.get("toolName"), "command": command})
    if decision.blocked:
        return _deny_pretool(event, f"HARNESS4CODEX git guard: {decision.reason}")
    if decision.warning:
        return _context_output(event, f"HARNESS4CODEX warning: {decision.warning}")
    return ""


def _handle_permission(payload: dict[str, Any], store: HarnessStateStore) -> str:
    command = _command_from_payload(payload)
    decision = inspect_command(command)
    store.log_event("PermissionRequest", {"command": command})
    if decision.blocked:
        return _deny_permission(f"HARNESS4CODEX git guard: {decision.reason}")
    if decision.warning:
        return _context_output("PermissionRequest", f"HARNESS4CODEX warning: {decision.warning}")
    return ""


def _handle_post_tool(event: str, payload: dict[str, Any], store: HarnessStateStore) -> str:
    command = _command_from_payload(payload)
    files = _extract_files(payload)
    state = store.load()
    promoted = False
    for file_path in files:
        before = state.get("level")
        state = store.record_file(file_path)
        promoted = promoted or (before == "C0" and state.get("level") == "C1")
    exit_code = _extract_exit_code(payload)
    verification_seen = _looks_like_verification(command)
    if verification_seen and exit_code == 0:
        state = store.mark_verified(command)
    store.log_event(event, {"command": command, "files": files, "exit_code": exit_code})
    if promoted:
        return _context_output(
            event,
            "HARNESS4CODEX promoted this task from C0 to C1 because edits touched three or more files. Use codex-harness-workflow and run verification-before-completion.",
        )
    if verification_seen and exit_code is None:
        return _context_output(
            event,
            "HARNESS4CODEX saw a verification command, but the hook could not confirm exit code 0. Read the tool output before marking the task verified.",
        )
    return ""


def _handle_stop(payload: dict[str, Any], store: HarnessStateStore) -> str:
    if payload.get("stop_hook_active") or payload.get("stopHookActive"):
        return ""
    state = store.load()
    if state.get("status") == "active" and state.get("pipeline") and not state.get("verified"):
        if int(state.get("stop_continuations") or 0) < 1:
            store.increment_stop_continuations()
            reason = (
                "HARNESS4CODEX verification gate: continue with codex-harness-workflow and run "
                "verification-before-completion before the final response."
            )
            store.log_event("Stop", {"blocked": True, "reason": reason})
            return _block_stop(reason)
    store.log_event("Stop", {"blocked": False, "status": state.get("status")})
    return ""


def handle_payload(payload: dict[str, Any], harness_home: str | Path | None = None) -> str:
    event = _event_name(payload)
    store = HarnessStateStore(harness_home)
    if event == "SessionStart":
        return _handle_session_start(event, store)
    if event == "UserPromptSubmit":
        return _handle_user_prompt(event, payload, store)
    if event == "PreToolUse":
        return _handle_pre_tool(event, payload, store)
    if event == "PermissionRequest":
        return _handle_permission(payload, store)
    if event == "PostToolUse":
        return _handle_post_tool(event, payload, store)
    if event == "Stop":
        return _handle_stop(payload, store)
    return ""


def _error_output(message: str) -> str:
    return _json({"continue": True, "systemMessage": f"HARNESS4CODEX hook error: {message}"})


def main() -> int:
    raw = sys.stdin.read()
    if not raw.strip():
        return 0
    try:
        payload = json.loads(raw)
        output = handle_payload(payload)
        if output:
            print(output)
        return 0
    except Exception as exc:  # pragma: no cover - defensive hook boundary
        store = HarnessStateStore()
        store.log_error(traceback.format_exc())
        print(_error_output(str(exc)))
        return 0
