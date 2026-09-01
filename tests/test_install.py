
import json
import shutil
import subprocess
from pathlib import Path

from scripts.install import (
    build_hooks_config,
    ensure_feature_flag,
    install,
    native_plugin_enabled,
)


def test_build_hooks_config_contains_all_core_events():
    config = build_hooks_config(r"C:\Users\me\.codex\plugins\harness4codex\hooks\codex_harness_hook.py")

    hooks = config["hooks"]
    assert {
        "SessionStart", "UserPromptSubmit", "PreToolUse", "PermissionRequest", "PostToolUse",
        "PreCompact", "PostCompact", "SubagentStart", "SubagentStop", "Stop", "SessionEnd",
    } <= set(hooks)
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


def test_native_plugin_detection_supports_codex_plugin_sections_without_tomllib():
    config = """
[plugins."documents@runtime"]
enabled = true
[plugins.'harness4codex@personal']
enabled = TRUE # native discovery
"""

    assert native_plugin_enabled(config) is True
    assert native_plugin_enabled(config.replace("TRUE", "false")) is False


def test_install_replaces_plugin_tree_without_leaving_stale_files(tmp_path):
    source = tmp_path / "source"
    (source / "hooks").mkdir(parents=True)
    (source / "hooks" / "codex_harness_hook.py").write_text("# hook\n", encoding="utf-8")
    (source / "skills" / "codex-harness-workflow").mkdir(parents=True)
    (source / "skills" / "codex-harness-workflow" / "SKILL.md").write_text("# skill\n", encoding="utf-8")
    (source / "skills" / "write-spec").mkdir(parents=True)
    (source / "skills" / "write-spec" / "SKILL.md").write_text("# spec\n", encoding="utf-8")
    codex_home = tmp_path / "codex"
    stale = codex_home / "plugins" / "harness4codex" / "stale.txt"
    stale.parent.mkdir(parents=True)
    stale.write_text("old", encoding="utf-8")

    install(source, codex_home)

    assert not stale.exists()
    assert (codex_home / "plugins" / "harness4codex" / "hooks" / "codex_harness_hook.py").exists()
    assert (codex_home / "skills" / "write-spec" / "SKILL.md").exists()
    assert not list((codex_home / "plugins").glob("*.staging-*"))
    assert not list((codex_home / "plugins").glob("*.backup-*"))


def test_install_uses_native_plugin_hooks_and_removes_legacy_duplicate(tmp_path):
    source = tmp_path / "source"
    (source / "hooks").mkdir(parents=True)
    (source / "hooks" / "codex_harness_hook.py").write_text("# hook\n", encoding="utf-8")
    (source / "skills" / "codex-harness-workflow").mkdir(parents=True)
    (source / "skills" / "codex-harness-workflow" / "SKILL.md").write_text("# skill\n", encoding="utf-8")
    codex_home = tmp_path / "codex"
    codex_home.mkdir()
    marketplace = tmp_path / "marketplace"
    (codex_home / "config.toml").write_text(
        '[marketplaces.personal]\nsource_type = "local"\n'
        f'source = "{marketplace.as_posix()}"\n'
        '[plugins."harness4codex@personal"]\nenabled = true\n',
        encoding="utf-8",
    )
    (codex_home / "hooks.json").write_text(
        json.dumps(
            {
                "hooks": {
                    "Stop": [
                        {"hooks": [{"type": "command", "command": "python /legacy/codex_harness_hook.py"}]},
                        {"hooks": [{"type": "command", "command": "python /third-party/hook.py"}]},
                    ]
                }
            }
        ),
        encoding="utf-8",
    )

    (source / ".codex-plugin").mkdir()
    (source / ".codex-plugin" / "plugin.json").write_text(
        json.dumps({"name": "harness4codex", "version": "1.0.0"}), encoding="utf-8"
    )
    (source / "hooks" / "hooks.json").write_text(
        json.dumps(build_hooks_config("hook.py")), encoding="utf-8"
    )
    commands = []

    def native_runner(command, home):
        commands.append(command)
        cached = home / "plugins" / "cache" / "personal" / "harness4codex" / "1.0.0"
        shutil.copytree(marketplace / "plugins" / "harness4codex", cached)
        return subprocess.CompletedProcess(command, 0, stdout="{}", stderr="")

    result = install(source, codex_home, native_runner=native_runner)

    installed = json.loads((codex_home / "hooks.json").read_text(encoding="utf-8"))
    hook_commands = [hook["command"] for entry in installed["hooks"]["Stop"] for hook in entry["hooks"]]
    assert result["hook_mode"] == "plugin"
    assert hook_commands == ["python /third-party/hook.py"]
    assert commands == [["codex", "plugin", "add", "harness4codex@personal", "--json"]]


def test_native_install_updates_local_marketplace_and_active_cache(tmp_path):
    source = tmp_path / "source"
    (source / ".codex-plugin").mkdir(parents=True)
    (source / ".codex-plugin" / "plugin.json").write_text(
        json.dumps({"name": "harness4codex", "version": "2.0.0"}), encoding="utf-8"
    )
    (source / "hooks").mkdir()
    (source / "hooks" / "hooks.json").write_text(
        json.dumps(build_hooks_config("hook.py")), encoding="utf-8"
    )
    (source / "hooks" / "codex_harness_hook.py").write_text("# hook\n", encoding="utf-8")
    (source / "skills" / "codex-harness-workflow").mkdir(parents=True)
    (source / "skills" / "codex-harness-workflow" / "SKILL.md").write_text("# skill\n", encoding="utf-8")
    codex_home = tmp_path / "codex"
    codex_home.mkdir()
    marketplace = tmp_path / "personal-marketplace"
    (codex_home / "config.toml").write_text(
        '[features]\nhooks = true\n'
        '[marketplaces.personal]\nsource_type = "local"\n'
        f'source = "{marketplace.as_posix()}"\n'
        '[plugins."harness4codex@personal"]\nenabled = true\n',
        encoding="utf-8",
    )
    invoked = []

    def native_runner(command, home):
        invoked.append((command, home))
        cached = home / "plugins" / "cache" / "personal" / "harness4codex" / "2.0.0"
        shutil.copytree(marketplace / "plugins" / "harness4codex", cached)
        return subprocess.CompletedProcess(command, 0, stdout='{"installed": true}', stderr="")

    result = install(source, codex_home, native_runner=native_runner)

    marketplace_plugin = marketplace / "plugins" / "harness4codex"
    assert json.loads((marketplace_plugin / ".codex-plugin" / "plugin.json").read_text())["version"] == "2.0.0"
    assert invoked == [(["codex", "plugin", "add", "harness4codex@personal", "--json"], codex_home)]
    assert Path(result["active_plugin"]) == (
        codex_home / "plugins" / "cache" / "personal" / "harness4codex" / "2.0.0"
    )


def test_install_uses_global_hooks_when_native_plugin_is_not_enabled(tmp_path):
    source = tmp_path / "source"
    (source / "hooks").mkdir(parents=True)
    (source / "hooks" / "codex_harness_hook.py").write_text("# hook\n", encoding="utf-8")
    (source / "skills" / "codex-harness-workflow").mkdir(parents=True)
    (source / "skills" / "codex-harness-workflow" / "SKILL.md").write_text("# skill\n", encoding="utf-8")
    codex_home = tmp_path / "codex"

    result = install(source, codex_home)

    installed = json.loads((codex_home / "hooks.json").read_text(encoding="utf-8"))
    commands = [hook["command"] for entry in installed["hooks"]["Stop"] for hook in entry["hooks"]]
    assert result["hook_mode"] == "global"
    assert len([command for command in commands if "codex_harness_hook.py" in command]) == 1
