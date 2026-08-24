import json

from harness4codex.hook import _decode_payload, _extract_exit_code, handle_payload
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
            "tool_input": {
                "command": "*** Update File: a.py\n*** Add File: b.py\n*** Update File: c.py\n"
            },
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
            "tool_response": {
                "content": [{"type": "text", "text": "Process exited with code 0\n75 passed"}]
            },
        },
        harness_home=tmp_path,
    )

    assert output == ""
    assert HarnessStateStore(tmp_path).load()["verified"] is True


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
    payload = _decode_payload(
        '{"hook_event_name":"UserPromptSubmit","prompt":"correção e ciência"}'.encode()
    )

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
