from __future__ import annotations

import hashlib
import json
import re
import sqlite3
import sys
import traceback
from pathlib import Path
from typing import Any

from .classifier import classify_prompt
from .git_guard import inspect_command
from .harness_lite_adapter import preview_for_prompt
from .memory import HarnessMemoryStore
from .science_adapter import science_context
from .state import HarnessStateStore, store_for_payload
from .workflow import load_workflow

VERIFICATION_PATTERNS = [
    r"^\s*(?:py|python(?:\.exe)?)\s+-m\s+(?:pytest|unittest)\b",
    r"^\s*pytest(?:\.exe)?\b",
    r"^\s*(?:npm|pnpm)\s+(?:run\s+)?test\b",
    r"^\s*yarn\s+test\b",
    r"^\s*cargo\s+test\b",
    r"^\s*go\s+test\b",
]

PATCH_FILE_PATTERN = re.compile(r"^\*\*\* (?:Add|Update|Delete) File: (.+)$", re.MULTILINE)


def _event_name(payload: dict[str, Any]) -> str:
    return str(payload.get("hook_event_name") or payload.get("hookEventName") or payload.get("event") or "")


def _json(data: dict[str, Any]) -> str:
    return json.dumps(data, ensure_ascii=False, sort_keys=True)


def _context_output(event: str, context: str) -> str:
    return _json({"hookSpecificOutput": {"hookEventName": event, "additionalContext": context}})


def _system_message(message: str) -> str:
    return _json({"systemMessage": message})


def _deny_pretool(event: str, reason: str) -> str:
    return _json(
        {
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
            "systemMessage": reason,
            "hookSpecificOutput": {
                "hookEventName": "PermissionRequest",
                "decision": {"behavior": "deny", "message": reason},
            },
        }
    )


def _block_stop(reason: str) -> str:
    return _json({"decision": "block", "reason": reason})


def _decode_payload(raw: bytes | str) -> dict[str, Any]:
    text = raw.decode("utf-8-sig") if isinstance(raw, bytes) else raw
    value = json.loads(text)
    if not isinstance(value, dict):
        raise TypeError("hook input must be a JSON object")
    return value


def _tool_input(payload: dict[str, Any]) -> dict[str, Any]:
    value = payload.get("tool_input") or payload.get("toolInput") or payload.get("input") or {}
    return value if isinstance(value, dict) else {"command": str(value)}


def _command_from_payload(payload: dict[str, Any]) -> str:
    tool_input = _tool_input(payload)
    command = tool_input.get("command") or tool_input.get("cmd") or tool_input.get("script")
    if command is None:
        return ""
    return str(command)


def _is_shell_tool(payload: dict[str, Any]) -> bool:
    name = str(payload.get("tool_name") or payload.get("toolName") or "").casefold()
    return name in {
        "bash",
        "shell",
        "shell_command",
        "powershell",
        "exec_command",
        "functions.exec",
        "functions.exec_command",
    }


def _extract_files(payload: dict[str, Any]) -> list[str]:
    tool_input = _tool_input(payload)
    files: list[str] = []
    for key in ("file_path", "path", "target_file"):
        value = tool_input.get(key)
        if value:
            files.append(str(value))
    command = _command_from_payload(payload)
    patch = tool_input.get("patch") or tool_input.get("input") or ""
    files.extend(match.strip() for match in PATCH_FILE_PATTERN.findall(command + "\n" + str(patch)))
    return list(dict.fromkeys(files))


def _has_unquoted_shell_composition(command: str) -> bool:
    quote: str | None = None
    escaped = False
    for index, character in enumerate(command):
        if escaped:
            escaped = False
            continue
        if quote:
            if character == "\\" and quote == '"':
                escaped = True
            elif character == quote:
                quote = None
            continue
        if character in {"'", '"'}:
            quote = character
            continue
        if character in {";", "|", "&", "\r", "\n", "`"}:
            return True
        if character == "$" and index + 1 < len(command) and command[index + 1] == "(":
            return True
    return quote is not None


def _looks_like_verification(command: str) -> bool:
    if not command or _has_unquoted_shell_composition(command):
        return False
    return any(re.search(pattern, command, re.IGNORECASE) for pattern in VERIFICATION_PATTERNS)


def _extract_exit_code(payload: dict[str, Any]) -> int | None:
    for key in ("exit_code", "exitCode", "status"):
        value = payload.get(key)
        if isinstance(value, int):
            return value
    response = payload.get("tool_response") or payload.get("toolResponse") or payload.get("output") or ""

    def walk(value: Any) -> int | None:
        if isinstance(value, dict):
            for key in ("exit_code", "exitCode"):
                code = value.get(key)
                if isinstance(code, int) and not isinstance(code, bool):
                    return code
            for nested in value.values():
                code = walk(nested)
                if code is not None:
                    return code
            return None
        if isinstance(value, (list, tuple)):
            for nested in value:
                code = walk(nested)
                if code is not None:
                    return code
            return None
        if isinstance(value, str):
            patterns = (
                r"Process exited with code\s+(-?\d+)",
                r"Exit code:\s*(-?\d+)",
                r"[\"']?exit_code[\"']?\s*[:=]\s*(-?\d+)",
                r"\bexit=(-?\d+)\b",
            )
            for pattern in patterns:
                match = re.search(pattern, value, re.IGNORECASE)
                if match:
                    return int(match.group(1))
        return None

    nested_code = walk(response)
    if nested_code is not None:
        return nested_code
    return None


def _response_text(payload: dict[str, Any]) -> str:
    response = payload.get("tool_response") or payload.get("toolResponse") or payload.get("output") or ""
    fragments: list[str] = []

    def walk(value: Any) -> None:
        if isinstance(value, str):
            fragments.append(value)
        elif isinstance(value, dict):
            for nested in value.values():
                walk(nested)
        elif isinstance(value, (list, tuple)):
            for nested in value:
                walk(nested)

    walk(response)
    return "\n".join(fragments)


def _extract_test_counts(payload: dict[str, Any]) -> tuple[int | None, int | None, str | None]:
    text = _response_text(payload)
    output_hash = hashlib.sha256(text.encode("utf-8")).hexdigest() if text else None
    if re.search(r"\b(no tests ran|collected 0 items|0 tests? (?:run|passed|total))\b", text, re.IGNORECASE):
        return 0, 0, output_hash
    total_match = re.search(r"\b(\d+)\s+passed\b[^\n]*\b(\d+)\s+total\b", text, re.IGNORECASE)
    if total_match:
        return int(total_match.group(2)), int(total_match.group(1)), output_hash
    passed = [int(value) for value in re.findall(r"\b(\d+)\s+passed\b", text, re.IGNORECASE)]
    failed = [int(value) for value in re.findall(r"\b(\d+)\s+failed\b", text, re.IGNORECASE)]
    errors = [int(value) for value in re.findall(r"\b(\d+)\s+errors?\b", text, re.IGNORECASE)]
    if passed or failed or errors:
        passed_count = max(passed, default=0)
        collected = passed_count + max(failed, default=0) + max(errors, default=0)
        return collected, passed_count, output_hash
    if re.search(r"\btest result:\s*ok\b", text, re.IGNORECASE):
        return 1, 1, output_hash
    if re.search(r"(?m)^ok\s+\S+", text):
        return 1, 1, output_hash
    return None, None, output_hash


def _task_context(state: dict[str, Any], heading: str) -> str:
    pipeline = state.get("pipeline") or []
    lines = [
        "HARNESS4CODEX",
        heading,
        f"Task: {state.get('task_id')}",
    ]
    if state.get("scope"):
        lines.append(f"Scope: {state.get('scope')}")
    if state.get("pending_gate"):
        lines.append(f"Pending human gate: {state.get('pending_gate')}")
    lines.extend(
        [
            f"Level: {state.get('level')} / {state.get('kind')}",
            "Skill: codex-harness-workflow",
            f"Pipeline: {', '.join(pipeline) if pipeline else 'none'}",
            (
                "Follow the listed skills in order. Do not claim completion until "
                "superpowers:verification-before-completion has fresh evidence."
            ),
        ]
    )
    return "\n".join(lines)


def _classification_context(state: dict[str, Any]) -> str:
    classification = state.get("classification") or {}
    reasons = classification.get("reasons") or []
    base = _task_context(state, "Classificacao criada para este turno.")
    if reasons:
        base += "\nReasons: " + ", ".join(reasons)
    return base


def _cwd_from_payload(payload: dict[str, Any]) -> Path:
    cwd = payload.get("cwd") or payload.get("working_directory") or payload.get("workingDirectory")
    if cwd:
        return Path(str(cwd))
    return Path.cwd()


def _append_workflow_context(context: str, payload: dict[str, Any]) -> str:
    try:
        workflow = load_workflow(_cwd_from_payload(payload))
    except (OSError, UnicodeError, ValueError):
        return context
    if workflow is None:
        return context
    return context + "\n\n" + workflow.render_for_prompt()


def _append_science_context(context: str, prompt: str) -> str:
    evidence = science_context(prompt)
    return context + ("\n\n" + evidence if evidence else "")


def _append_lite_preview(
    context: str,
    classification_level: str,
    prompt: str,
    payload: dict[str, Any],
    store: HarnessStateStore,
) -> str:
    result = preview_for_prompt(
        level=classification_level,
        objective=prompt,
        workspace_path=_cwd_from_payload(payload),
        session_id=str(payload.get("session_id") or payload.get("sessionId") or store.scope or "local"),
    )
    if result is None:
        return context
    if result.ok:
        route = result.result or {}
        summary = (
            "HARNESS LITE preview (advisory): "
            f"eligible={route.get('eligible')}, risk={route.get('riskTier')}, "
            f"runner={route.get('runner')}, model={route.get('modelAlias')}."
        )
        store.log_event("HarnessLitePreview", {"ok": True, "route": route})
    else:
        summary = f"HARNESS LITE preview unavailable: {result.code or 'CONTROL_ERROR'}."
        store.log_event("HarnessLitePreview", {"ok": False, "code": result.code, "status": result.status})
    return context + "\n\n" + summary


def _record_memory(store: HarnessStateStore, event: str, text: str, metadata: dict[str, Any]) -> None:
    try:
        HarnessMemoryStore(store.memory_home).record_history(event, text, metadata)
    except (OSError, sqlite3.Error, TypeError, ValueError) as exc:
        # Hooks must not fail task execution because auxiliary memory storage failed.
        store.log_error(f"memory record failed for {event}: {type(exc).__name__}: {exc}")


def _handle_session_start(event: str, store: HarnessStateStore) -> str:
    store.expire_stale_pipeline()
    state = store.load()
    if state.get("status") in {"active", "verified"} and state.get("pipeline"):
        return _context_output(event, _task_context(state, "Retome o pipeline ativo."))
    return ""


def _handle_user_prompt(event: str, payload: dict[str, Any], store: HarnessStateStore) -> str:
    prompt = str(payload.get("prompt") or payload.get("user_prompt") or payload.get("message") or "")
    classification = classify_prompt(prompt)
    store.expire_stale_pipeline()
    current = store.load()
    if current.get("status") in {"active", "awaiting_gate"} and not classification.is_task_switch:
        store.log_event(event, {"continued": current.get("task_id"), "prompt": prompt})
        _record_memory(store, event, prompt, {"continued": current.get("task_id")})
        heading = (
            f"Resolve the pending human gate {current.get('pending_gate')}."
            if current.get("status") == "awaiting_gate"
            else "Continue o pipeline ativo."
        )
        context = _append_workflow_context(_task_context(current, heading), payload)
        return _context_output(event, _append_science_context(context, prompt))
    state = store.start_task(classification, prompt)
    store.log_event(event, {"classification": state.get("classification"), "prompt": prompt})
    _record_memory(store, event, prompt, {"classification": state.get("classification")})
    context = _append_workflow_context(_classification_context(state), payload)
    context = _append_science_context(context, prompt)
    context = _append_lite_preview(context, classification.level, prompt, payload, store)
    return _context_output(event, context)


def _handle_pre_tool(event: str, payload: dict[str, Any], store: HarnessStateStore) -> str:
    command = _command_from_payload(payload)
    decision = inspect_command(command)
    store.log_event(event, {"tool": payload.get("tool_name") or payload.get("toolName"), "command": command})
    _record_memory(store, event, command, {"tool": payload.get("tool_name") or payload.get("toolName")})
    if decision.blocked:
        return _deny_pretool(event, f"HARNESS4CODEX git guard: {decision.reason}")
    if decision.warning:
        return _context_output(event, f"HARNESS4CODEX warning: {decision.warning}")
    return ""


def _handle_permission(payload: dict[str, Any], store: HarnessStateStore) -> str:
    command = _command_from_payload(payload)
    decision = inspect_command(command)
    store.log_event("PermissionRequest", {"command": command})
    _record_memory(store, "PermissionRequest", command, {})
    if decision.blocked:
        return _deny_permission(f"HARNESS4CODEX git guard: {decision.reason}")
    if decision.warning:
        return _system_message(f"HARNESS4CODEX warning: {decision.warning}")
    return ""


def _handle_post_tool(event: str, payload: dict[str, Any], store: HarnessStateStore) -> str:
    command = _command_from_payload(payload)
    files = _extract_files(payload)
    state = store.load()
    promoted = False
    if command and _is_shell_tool(payload):
        state = store.record_change_marker("shell-command")
    for file_path in files:
        before = state.get("level")
        state = store.record_file(file_path)
        promoted = promoted or (before == "C0" and state.get("level") == "C1")
    exit_code = _extract_exit_code(payload)
    verification_seen = _looks_like_verification(command)
    tests_collected, tests_passed, output_hash = _extract_test_counts(payload)
    if verification_seen:
        state = store.record_verification(
            command,
            exit_code=exit_code,
            tests_collected=tests_collected,
            tests_passed=tests_passed,
            output_hash=output_hash,
        )
    store.log_event(event, {"command": command, "files": files, "exit_code": exit_code})
    _record_memory(store, event, command or ", ".join(files), {"files": files, "exit_code": exit_code})
    if promoted:
        return _context_output(
            event,
            "HARNESS4CODEX promoted this task from C0 to C1 because edits touched "
            "three or more files. Use codex-harness-workflow and run "
            "verification-before-completion.",
        )
    if verification_seen and exit_code is None:
        return _context_output(
            event,
            "HARNESS4CODEX saw a verification command, but the hook could not confirm "
            "exit code 0. Read the tool output before marking the task verified.",
        )
    if verification_seen and exit_code == 0 and tests_collected == 0:
        return _context_output(
            event,
            "HARNESS4CODEX verification evidence rejected because the command collected zero tests.",
        )
    if verification_seen and exit_code == 0 and tests_collected is None:
        return _context_output(
            event,
            "HARNESS4CODEX could not establish how many tests ran; attach explicit verification evidence.",
        )
    return ""


def _handle_stop(payload: dict[str, Any], store: HarnessStateStore) -> str:
    if payload.get("stop_hook_active") or payload.get("stopHookActive"):
        return ""
    state = store.load()
    if state.get("status") == "active" and state.get("pipeline") and not state.get("verified"):
        continuations = int(state.get("stop_continuations") or 0)
        if continuations >= 2:
            store.set_pending_gate("escalation")
            reason = (
                "HARNESS4CODEX escalation gate: verification remains incomplete after two continuations. "
                "Ask the user for direction with the concrete blocker and evidence."
            )
            store.log_event("Stop", {"blocked": True, "reason": reason, "gate": "escalation"})
            return _block_stop(reason)
        store.increment_stop_continuations()
        reason = (
            "HARNESS4CODEX verification gate: continue with codex-harness-workflow and run "
            "superpowers:verification-before-completion before the final response."
        )
        store.log_event("Stop", {"blocked": True, "reason": reason})
        return _block_stop(reason)
    store.log_event("Stop", {"blocked": False, "status": state.get("status")})
    return ""


def _handle_compaction(event: str, store: HarnessStateStore) -> str:
    state = store.load()
    store.log_event(event, {"task_id": state.get("task_id"), "phase": state.get("current_step")})
    if state.get("status") in {"active", "verified", "awaiting_gate"}:
        return _context_output(event, _task_context(state, "Preserve this pipeline handoff across compaction."))
    return ""


def _handle_subagent(event: str, payload: dict[str, Any], store: HarnessStateStore) -> str:
    agent_id = payload.get("agent_id") or payload.get("agentId") or payload.get("subagent_id")
    store.log_event(event, {"agent_id": agent_id, "agent_type": payload.get("agent_type")})
    if event == "SubagentStart":
        return _context_output(
            event,
            "HARNESS4CODEX node contract: return role, status, findings, evidence_refs, coverage, and errors.",
        )
    return ""


def handle_payload(payload: dict[str, Any], harness_home: str | Path | None = None) -> str:
    event = _event_name(payload)
    store = store_for_payload(payload, harness_home)
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
    if event in {"PreCompact", "PostCompact"}:
        return _handle_compaction(event, store)
    if event in {"SubagentStart", "SubagentStop"}:
        return _handle_subagent(event, payload, store)
    if event == "Stop":
        return _handle_stop(payload, store)
    if event == "SessionEnd":
        store.log_event(event, {"reason": payload.get("reason")})
        return ""
    return ""


def _error_output(message: str) -> str:
    return _system_message(f"HARNESS4CODEX hook error: {message}")


def _emit(output: str) -> None:
    encoded = (output + "\n").encode("utf-8")
    buffer = getattr(sys.stdout, "buffer", None)
    if buffer is not None:
        buffer.write(encoded)
        buffer.flush()
    else:  # pragma: no cover - StringIO and embedded runtimes
        sys.stdout.write(encoded.decode("utf-8"))
        sys.stdout.flush()


def _log_boundary_error() -> None:
    try:
        HarnessStateStore().log_error(traceback.format_exc())
    except Exception:
        return


def main() -> int:
    raw = sys.stdin.buffer.read()
    if not raw.strip():
        return 0
    try:
        payload = _decode_payload(raw)
        output = handle_payload(payload)
        if output:
            _emit(output)
        return 0
    except Exception as exc:  # pragma: no cover - defensive hook boundary
        _log_boundary_error()
        _emit(_error_output(str(exc)))
        return 0
