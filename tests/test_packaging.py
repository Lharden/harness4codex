import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_plugin_manifest_points_to_skill_and_hooks():
    manifest = json.loads((ROOT / ".codex-plugin" / "plugin.json").read_text(encoding="utf-8"))

    assert manifest["name"] == "harness4codex"
    assert manifest["skills"] == "./skills/"
    assert manifest["hooks"] == "./hooks.json"


def test_codex_harness_skill_metadata_is_triggerable():
    skill = (ROOT / "skills" / "codex-harness-workflow" / "SKILL.md").read_text(encoding="utf-8")

    assert "name: codex-harness-workflow" in skill
    assert "Use when" in skill
    assert "HARNESS4CODEX" in skill


def test_hook_wrapper_imports_runtime():
    hook = (ROOT / "hooks" / "codex_harness_hook.py").read_text(encoding="utf-8")

    assert "harness4codex.hook" in hook
