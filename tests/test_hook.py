import json

from harness4codex.hook import handle_payload


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


def test_session_start_resumes_active_pipeline(tmp_path):
    handle_payload(
        {"hook_event_name": "UserPromptSubmit", "prompt": "Corrija bug de login."},
        harness_home=tmp_path,
    )

    output = handle_payload({"hook_event_name": "SessionStart", "source": "resume"}, harness_home=tmp_path)

    assert "Retome o pipeline" in _decode(output)["hookSpecificOutput"]["additionalContext"]


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


def test_stop_hook_active_does_not_loop(tmp_path):
    output = handle_payload({"hook_event_name": "Stop", "stop_hook_active": True}, harness_home=tmp_path)

    assert output == ""
