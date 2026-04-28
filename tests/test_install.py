from scripts.install import build_hooks_config, ensure_feature_flag


def test_build_hooks_config_contains_all_core_events():
    config = build_hooks_config(r"C:\Users\me\.codex\plugins\harness4codex\hooks\codex_harness_hook.py")

    hooks = config["hooks"]
    assert {"SessionStart", "UserPromptSubmit", "PreToolUse", "PermissionRequest", "PostToolUse", "Stop"} <= set(hooks)
    stop_command = hooks["Stop"][0]["hooks"][0]["command"]
    assert stop_command.startswith("python ")
    assert "codex_harness_hook.py" in stop_command


def test_ensure_feature_flag_adds_missing_features_section():
    result = ensure_feature_flag("")

    assert "[features]" in result
    assert "codex_hooks = true" in result


def test_ensure_feature_flag_updates_existing_value_and_preserves_other_flags():
    text = "[features]\ncodex_hooks = false\nmulti_agent = true\n"

    result = ensure_feature_flag(text)

    assert "codex_hooks = true" in result
    assert "multi_agent = true" in result
    assert "codex_hooks = false" not in result
