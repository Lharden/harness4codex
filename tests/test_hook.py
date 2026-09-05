import json
import sqlite3

import pytest

from harness4codex.hook import (
    _decode_payload,
    _extract_exit_code,
    _is_shell_tool,
    _looks_like_verification,
    handle_payload,
)
from harness4codex.memory import HarnessMemoryStore
from harness4codex.state import HarnessStateStore


def _decode(output: str) -> dict:
    assert output
    return json.loads(output)


def test_user_prompt_submit_injects_harness_context(tmp_path):
    output = handle_payload(
        {
            "hook_event_name": "UserPromptSubmit",
            "prompt": "Implemente exportacao CSV.",
        },
        harness_home=tmp_path,
    )

    data = _decode(output)
    context = data["hookSpecificOutput"]["additionalContext"]
    assert "HARNESS4CODEX" in context
    assert "codex-harness-workflow" in context


def test_user_prompt_submit_includes_repo_workflow_context(tmp_path):
    repo = tmp_path / "repo"
    repo.mkdir()
    (repo / "WORKFLOW.md").write_text(
        "---\nverification:\n  commands:\n    - pytest -q\nhandoff_state: Human Review\n---\n"
        "# Workflow\nAttach proof before review.\n",
        encoding="utf-8",
    )

    output = handle_payload(
        {
            "hook_event_name": "UserPromptSubmit",
            "prompt": "Implemente exportacao CSV.",
            "cwd": str(repo),
        },
        harness_home=tmp_path / "home",
    )

    context = _decode(output)["hookSpecificOutput"]["additionalContext"]
    assert "Repo WORKFLOW.md" in context
    assert "pytest -q" in context
    assert "Human Review" in context


def test_session_start_resumes_active_pipeline(tmp_path):
    handle_payload(
        {"hook_event_name": "UserPromptSubmit", "prompt": "Corrija bug de login."},
        harness_home=tmp_path,
    )

    output = handle_payload({"hook_event_name": "SessionStart", "source": "resume"}, harness_home=tmp_path)

    assert "Retome o pipeline" in _decode(output)["hookSpecificOutput"]["additionalContext"]


def test_session_start_expires_stale_pipeline_before_resuming(tmp_path):
    handle_payload(
        {"hook_event_name": "UserPromptSubmit", "prompt": "Corrija bug de login."},
        harness_home=tmp_path,
    )
    state_path = tmp_path / "state.json"
    state = json.loads(state_path.read_text(encoding="utf-8"))
    state["started_at"] = "2000-01-01T00:00:00+00:00"
    state_path.write_text(json.dumps(state), encoding="utf-8")
    with sqlite3.connect(tmp_path / "harness.db") as connection:
        connection.execute(
            "UPDATE tasks SET started_at = ? WHERE task_id = ?",
            ("2000-01-01T00:00:00+00:00", state["task_id"]),
        )

    output = handle_payload({"hook_event_name": "SessionStart", "source": "resume"}, harness_home=tmp_path)

    assert output == ""
    expired = HarnessStateStore(tmp_path).load()
    assert expired["status"] == "idle"
    assert expired["task_id"] is None


def test_user_response_continues_pending_gate_instead_of_starting_new_task(tmp_path):
    store = HarnessStateStore(tmp_path)
    handle_payload(
        {"hook_event_name": "UserPromptSubmit", "prompt": "Implemente exportacao CSV."},
        harness_home=tmp_path,
    )
    waiting = store.set_pending_gate("approve-plan")

    output = handle_payload(
        {"hook_event_name": "UserPromptSubmit", "prompt": "Aprovo o plano."},
        harness_home=tmp_path,
    )

    current = store.load()
    assert current["task_id"] == waiting["task_id"]
    assert current["status"] == "awaiting_gate"
    context = _decode(output)["hookSpecificOutput"]["additionalContext"]
    assert "approve-plan" in context
    assert "Resolve" in context


def test_parallel_sessions_do_not_continue_each_other(tmp_path):
    repo = tmp_path / "repo"
    repo.mkdir()
    handle_payload(
        {
            "hook_event_name": "UserPromptSubmit",
            "session_id": "session-a",
            "cwd": str(repo),
            "prompt": "Implemente exportacao CSV.",
        },
        harness_home=tmp_path,
    )

    output = handle_payload(
        {
            "hook_event_name": "UserPromptSubmit",
            "session_id": "session-b",
            "cwd": str(repo),
            "prompt": "Explique este modulo.",
        },
        harness_home=tmp_path,
    )

    context = _decode(output)["hookSpecificOutput"]["additionalContext"]
    assert "Classificacao criada" in context
    assert "Continue o pipeline ativo" not in context
    assert "Level: C0 / question" in context


def test_stop_gate_is_scoped_to_session(tmp_path):
    repo = tmp_path / "repo"
    repo.mkdir()
    handle_payload(
        {
            "hook_event_name": "UserPromptSubmit",
            "session_id": "session-a",
            "cwd": str(repo),
            "prompt": "Implemente exportacao CSV.",
        },
        harness_home=tmp_path,
    )

    output = handle_payload(
        {"hook_event_name": "Stop", "session_id": "session-b", "cwd": str(repo)},
        harness_home=tmp_path,
    )

    assert output == ""


def test_pre_tool_use_denies_dangerous_git(tmp_path):
    output = handle_payload(
        {
            "hook_event_name": "PreToolUse",
            "tool_name": "Bash",
            "tool_input": {"command": "git reset --hard HEAD~1"},
        },
        harness_home=tmp_path,
    )

    data = _decode(output)
    assert data["hookSpecificOutput"]["permissionDecision"] == "deny"
    assert set(data) == {"systemMessage", "hookSpecificOutput"}
    assert set(data["hookSpecificOutput"]) == {
        "hookEventName",
        "permissionDecision",
        "permissionDecisionReason",
    }


def test_permission_request_denies_dangerous_git(tmp_path):
    output = handle_payload(
        {
            "hook_event_name": "PermissionRequest",
            "tool_name": "Bash",
            "tool_input": {"command": "git push --force"},
        },
        harness_home=tmp_path,
    )

    data = _decode(output)
    assert data["hookSpecificOutput"]["decision"]["behavior"] == "deny"
    assert set(data) == {"systemMessage", "hookSpecificOutput"}
    assert set(data["hookSpecificOutput"]) == {"hookEventName", "decision"}


def test_permission_request_warning_uses_only_a_generic_system_message(tmp_path):
    output = handle_payload(
        {
            "hook_event_name": "PermissionRequest",
            "tool_name": "Bash",
            "tool_input": {"command": "git push origin feature"},
        },
        harness_home=tmp_path,
    )

    data = _decode(output)
    assert set(data) == {"systemMessage"}
    assert "confirm" in data["systemMessage"].lower()


def test_post_tool_use_promotes_after_multiple_files(tmp_path):
    handle_payload(
        {"hook_event_name": "UserPromptSubmit", "prompt": "Explique este modulo."},
        harness_home=tmp_path,
    )
    output = handle_payload(
        {
            "hook_event_name": "PostToolUse",
            "tool_name": "apply_patch",
            "tool_input": {"command": "*** Update File: a.py\n*** Add File: b.py\n*** Update File: c.py\n"},
        },
        harness_home=tmp_path,
    )

    assert "promoted" in _decode(output)["hookSpecificOutput"]["additionalContext"].lower()


def test_stop_blocks_unverified_active_pipeline_once(tmp_path):
    handle_payload(
        {"hook_event_name": "UserPromptSubmit", "prompt": "Implemente exportacao CSV."},
        harness_home=tmp_path,
    )

    output = handle_payload({"hook_event_name": "Stop"}, harness_home=tmp_path)

    data = _decode(output)
    assert data["decision"] == "block"
    assert "verification" in data["reason"].lower()


def test_stop_keeps_blocking_until_fresh_verification(tmp_path):
    handle_payload(
        {"hook_event_name": "UserPromptSubmit", "prompt": "Implemente exportacao CSV."},
        harness_home=tmp_path,
    )

    first = _decode(handle_payload({"hook_event_name": "Stop"}, harness_home=tmp_path))
    second = _decode(handle_payload({"hook_event_name": "Stop"}, harness_home=tmp_path))

    assert first["decision"] == second["decision"] == "block"


def test_stop_block_output_uses_codex_stop_schema_only(tmp_path):
    handle_payload(
        {"hook_event_name": "UserPromptSubmit", "prompt": "Implemente exportacao CSV."},
        harness_home=tmp_path,
    )

    output = handle_payload({"hook_event_name": "Stop"}, harness_home=tmp_path)

    data = _decode(output)
    assert set(data) == {"decision", "reason"}
    assert data["decision"] == "block"
    assert data["reason"].strip()
    assert "hookSpecificOutput" not in data


def test_stop_hook_active_does_not_loop(tmp_path):
    output = handle_payload({"hook_event_name": "Stop", "stop_hook_active": True}, harness_home=tmp_path)

    assert output == ""


def test_extract_exit_code_from_current_nested_tool_response():
    payload = {
        "tool_response": {
            "content": [
                {
                    "type": "text",
                    "text": "Script completed\nProcess exited with code 0\nFinal output:\n75 passed",
                }
            ]
        }
    }

    assert _extract_exit_code(payload) == 0


def test_successful_verification_is_recorded_from_nested_response(tmp_path):
    handle_payload(
        {"hook_event_name": "UserPromptSubmit", "prompt": "Corrija o bug."},
        harness_home=tmp_path,
    )

    output = handle_payload(
        {
            "hook_event_name": "PostToolUse",
            "tool_name": "Bash",
            "tool_input": {"cmd": "python -m pytest -q"},
            "tool_response": {"content": [{"type": "text", "text": "Process exited with code 0\n75 passed"}]},
        },
        harness_home=tmp_path,
    )

    assert output == ""
    assert HarnessStateStore(tmp_path).load()["verified"] is True


def test_verification_detection_requires_an_actual_test_runner_command():
    assert _looks_like_verification("python -m pytest -q") is True
    assert _looks_like_verification("npm run test") is True
    assert _looks_like_verification("echo pytest 1 passed") is False
    assert _looks_like_verification("python -c \"print('pytest 1 passed')\"") is False
    assert _is_shell_tool({"tool_name": "shell_command"}) is True
    assert _is_shell_tool({"tool_name": "exec_command"}) is True
    assert _is_shell_tool({"tool_name": "functions.exec"}) is True


@pytest.mark.parametrize(
    "command",
    [
        "python -m pytest --invalid-option; echo '1 passed'",
        "python -m pytest --invalid-option && echo '1 passed'",
        "python -m pytest --invalid-option || echo '1 passed'",
        "python -m pytest --invalid-option | echo '1 passed'",
        "python -m pytest --invalid-option\necho '1 passed'",
    ],
)
def test_composed_shell_command_is_not_trusted_verification(command):
    assert _looks_like_verification(command) is False


def test_composed_command_cannot_create_automatic_test_evidence(tmp_path):
    handle_payload(
        {"hook_event_name": "UserPromptSubmit", "prompt": "Corrija o bug."},
        harness_home=tmp_path,
    )

    handle_payload(
        {
            "hook_event_name": "PostToolUse",
            "tool_name": "Bash",
            "tool_input": {"cmd": "python -m pytest --invalid-option; echo '1 passed'"},
            "tool_response": {"content": [{"type": "text", "text": "Process exited with code 0\n1 passed"}]},
        },
        harness_home=tmp_path,
    )

    assert HarnessStateStore(tmp_path).load()["verified"] is False


def test_shell_command_invalidates_prior_evidence_without_promoting_file_count(tmp_path):
    store = HarnessStateStore(tmp_path)
    handle_payload(
        {"hook_event_name": "UserPromptSubmit", "prompt": "Corrija o bug."},
        harness_home=tmp_path,
    )
    store.mark_verified("python -m pytest -q")
    before = store.load()

    handle_payload(
        {
            "hook_event_name": "PostToolUse",
            "tool_name": "shell_command",
            "tool_input": {"cmd": "sed -i s/old/new/ app.py"},
            "tool_response": {"exit_code": 0, "output": ""},
        },
        harness_home=tmp_path,
    )

    after = store.load()
    assert after["verified"] is False
    assert after["code_revision"] == before["code_revision"] + 1
    assert after["files"] == before["files"]


def test_zero_collected_tests_do_not_satisfy_stop_gate(tmp_path):
    handle_payload(
        {"hook_event_name": "UserPromptSubmit", "prompt": "Corrija o bug."},
        harness_home=tmp_path,
    )

    handle_payload(
        {
            "hook_event_name": "PostToolUse",
            "tool_name": "Bash",
            "tool_input": {"cmd": "python -m pytest -q"},
            "tool_response": {"content": [{"type": "text", "text": "Process exited with code 0\nno tests ran"}]},
        },
        harness_home=tmp_path,
    )

    assert HarnessStateStore(tmp_path).load()["verified"] is False
    assert _decode(handle_payload({"hook_event_name": "Stop"}, harness_home=tmp_path))["decision"] == "block"


def test_stop_escalates_after_two_automatic_continuations_then_allows_human_gate(tmp_path):
    handle_payload(
        {"hook_event_name": "UserPromptSubmit", "prompt": "Implemente exportacao CSV."},
        harness_home=tmp_path,
    )

    assert _decode(handle_payload({"hook_event_name": "Stop"}, harness_home=tmp_path))["decision"] == "block"
    assert _decode(handle_payload({"hook_event_name": "Stop"}, harness_home=tmp_path))["decision"] == "block"
    escalation = _decode(handle_payload({"hook_event_name": "Stop"}, harness_home=tmp_path))

    assert escalation["decision"] == "block"
    assert "user" in escalation["reason"].lower()
    state = HarnessStateStore(tmp_path).load()
    assert state["status"] == "awaiting_gate"
    assert state["pending_gate"] == "escalation"
    assert handle_payload({"hook_event_name": "Stop"}, harness_home=tmp_path) == ""


def test_write_after_verification_invalidates_the_gate(tmp_path):
    store = HarnessStateStore(tmp_path)
    handle_payload(
        {"hook_event_name": "UserPromptSubmit", "prompt": "Corrija o bug."},
        harness_home=tmp_path,
    )
    store.mark_verified("python -m pytest -q")

    handle_payload(
        {
            "hook_event_name": "PostToolUse",
            "tool_name": "apply_patch",
            "tool_input": {"patch": "*** Update File: app.py\n"},
        },
        harness_home=tmp_path,
    )

    state = store.load()
    assert state["verified"] is False
    assert state["status"] == "active"


def test_utf8_hook_input_is_decoded_independently_of_windows_stdio():
    payload = _decode_payload('{"hook_event_name":"UserPromptSubmit","prompt":"correção e ciência"}'.encode())

    assert payload["prompt"] == "correção e ciência"


def test_session_history_is_recorded_in_the_shared_memory_store(tmp_path):
    handle_payload(
        {
            "hook_event_name": "UserPromptSubmit",
            "session_id": "session-a",
            "cwd": str(tmp_path),
            "prompt": "Corrija o bug de autenticação.",
        },
        harness_home=tmp_path,
    )

    assert HarnessMemoryStore(tmp_path).history_count() == 1


def test_science_evidence_intent_is_added_to_prompt_context(tmp_path):
    output = handle_payload(
        {
            "hook_event_name": "UserPromptSubmit",
            "prompt": "Analise as evidências científicas e claims do corpus.",
        },
        harness_home=tmp_path,
    )

    context = _decode(output)["hookSpecificOutput"]["additionalContext"]
    assert "science_harness" in context
    assert "read-only" in context
