import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_plugin_manifest_points_to_skill_and_hooks():
    manifest = json.loads((ROOT / ".codex-plugin" / "plugin.json").read_text(encoding="utf-8"))

    assert manifest["name"] == "harness4codex"
    assert manifest["skills"] == "./skills/"
    assert "hooks" not in manifest
    assert (ROOT / "hooks" / "hooks.json").exists()


def test_codex_harness_skill_metadata_is_triggerable():
    skill = (ROOT / "skills" / "codex-harness-workflow" / "SKILL.md").read_text(encoding="utf-8")

    assert "name: codex-harness-workflow" in skill
    assert "Use when" in skill
    assert "HARNESS4CODEX" in skill


def test_hook_wrapper_imports_runtime():
    hook = (ROOT / "hooks" / "codex_harness_hook.py").read_text(encoding="utf-8")

    assert "harness4codex.hook" in hook


def test_skill_agent_metadata_uses_interface_schema():
    metadata = (ROOT / "skills" / "codex-harness-workflow" / "agents" / "openai.yaml").read_text(encoding="utf-8")

    assert metadata.startswith("interface:\n")
    assert "  display_name:" in metadata
    assert "  short_description:" in metadata
    assert "  default_prompt:" in metadata


def test_plugin_hook_uses_portable_plugin_root_commands():
    config = json.loads((ROOT / "hooks" / "hooks.json").read_text(encoding="utf-8"))
    command_hook = config["hooks"]["UserPromptSubmit"][0]["hooks"][0]

    assert "PLUGIN_ROOT" in command_hook["command"]
    assert "commandWindows" in command_hook


def test_plugin_registers_full_codex_lifecycle():
    config = json.loads((ROOT / "hooks" / "hooks.json").read_text(encoding="utf-8"))

    assert {
        "SessionStart",
        "UserPromptSubmit",
        "PreToolUse",
        "PermissionRequest",
        "PostToolUse",
        "PreCompact",
        "PostCompact",
        "SubagentStart",
        "SubagentStop",
        "Stop",
        "SessionEnd",
    } <= set(config["hooks"])
