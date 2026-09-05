import json
from pathlib import Path

try:
    import tomllib
except ModuleNotFoundError:  # pragma: no cover - exercised by the Python 3.10 CI job
    import tomli as tomllib

from harness4codex import __version__

ROOT = Path(__file__).resolve().parents[1]

SDD_SKILLS = {
    "discuss",
    "write-spec-light",
    "write-spec",
    "grill-me",
    "design-doc",
    "validate-plan",
    "verify-against-spec",
    "graph-context",
    "branch-out",
    "assimilar",
    "wiki-query",
    "compress-memory",
    "security-scan-python",
}


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

    post_tool_matcher = config["hooks"]["PostToolUse"][0]["matcher"]
    assert "shell_command" in post_tool_matcher
    assert "exec_command" in post_tool_matcher


def test_codex_native_sdd_skill_surface_is_packaged():
    for name in SDD_SKILLS:
        path = ROOT / "skills" / name / "SKILL.md"
        assert path.exists(), name
        text = path.read_text(encoding="utf-8")
        assert f"name: {name}" in text
        assert "Harness4Codex" in text


def test_codex_skills_do_not_depend_on_claude_host_primitives():
    forbidden = ("$CLAUDE_PLUGIN_ROOT", "AskUserQuestion", "Workflow({", "~/.claude")
    for path in (ROOT / "skills").glob("*/SKILL.md"):
        text = path.read_text(encoding="utf-8")
        for marker in forbidden:
            assert marker not in text, f"{path}: {marker}"


def test_sdd_templates_are_packaged():
    expected = {
        "write-spec-light": "spec-light-template.md",
        "write-spec": "spec-template.md",
        "design-doc": "design-template.md",
        "verify-against-spec": "verification-template.md",
        "branch-out": "branch-seed-template.md",
    }
    for skill, template in expected.items():
        assert (ROOT / "skills" / skill / "templates" / template).exists()


def test_workflow_skill_drives_the_transactional_contract():
    text = (ROOT / "skills" / "codex-harness-workflow" / "SKILL.md").read_text(encoding="utf-8")

    for marker in (
        "classification confirm",
        "artifact record",
        "task transition",
        "evidence record",
        "task complete",
        "approve-spec",
        "approve-plan",
        "NodeResult",
        "DROP / CONSTRAIN / RETAIN",
    ):
        assert marker in text


def test_release_version_is_synchronized():
    manifest = json.loads((ROOT / ".codex-plugin" / "plugin.json").read_text(encoding="utf-8"))
    with (ROOT / "pyproject.toml").open("rb") as handle:
        project = tomllib.load(handle)

    assert manifest["version"] == project["project"]["version"] == __version__ == "1.1.0"
