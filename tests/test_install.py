
from scripts.install import build_hooks_config, ensure_feature_flag, install


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
    assert "hooks = true" in result


def test_ensure_feature_flag_updates_existing_value_and_preserves_other_flags():
    text = "[features]\ncodex_hooks = false\nhooks = false\nmulti_agent = true\n"

    result = ensure_feature_flag(text)

    assert "hooks = true" in result
    assert "multi_agent = true" in result
    assert "codex_hooks" not in result


def test_install_replaces_plugin_tree_without_leaving_stale_files(tmp_path):
    source = tmp_path / "source"
    (source / "hooks").mkdir(parents=True)
    (source / "hooks" / "codex_harness_hook.py").write_text("# hook\n", encoding="utf-8")
    (source / "skills" / "codex-harness-workflow").mkdir(parents=True)
    (source / "skills" / "codex-harness-workflow" / "SKILL.md").write_text("# skill\n", encoding="utf-8")
    codex_home = tmp_path / "codex"
    stale = codex_home / "plugins" / "harness4codex" / "stale.txt"
    stale.parent.mkdir(parents=True)
    stale.write_text("old", encoding="utf-8")

    install(source, codex_home)

    assert not stale.exists()
    assert (codex_home / "plugins" / "harness4codex" / "hooks" / "codex_harness_hook.py").exists()
    assert not list((codex_home / "plugins").glob("*.staging-*"))
    assert not list((codex_home / "plugins").glob("*.backup-*"))
