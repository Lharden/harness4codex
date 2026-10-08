import json
import re
import shlex
from pathlib import Path

import pytest

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


def test_plugin_hook_commands_resolve_under_the_codex_windows_shell():
    """B-18: o comando que o Windows executa precisa achar o plugin.

    Medido em 2026-09-23 com o Codex 0.155.1: no Windows o `commandWindows`
    substitui o `command` e roda no PowerShell Core. `%PLUGIN_ROOT%` e sintaxe
    do cmd e chegava literal ao python, que nao achava o arquivo; os onze
    eventos falhavam em toda sessao desde 9fbb71b (24/08). O teste anterior
    exigia `commandWindows` e por isso aprovava o defeito.

    `${PLUGIN_ROOT}` e substituido pelo proprio Codex antes de executar, e e
    o que faz os hooks do `remember` funcionarem nesta maquina.
    """
    config = json.loads((ROOT / "hooks" / "hooks.json").read_text(encoding="utf-8"))

    for event, groups in config["hooks"].items():
        for group in groups:
            for handler in group["hooks"]:
                windows_command = handler.get("commandWindows", handler["command"])
                assert "${PLUGIN_ROOT}" in windows_command, event
                assert not re.search(r"%[A-Za-z_][A-Za-z0-9_]*%", windows_command), event


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


def test_subagent_stop_hook_label_does_not_claim_a_census():
    import json
    from pathlib import Path

    hooks = json.loads((Path(__file__).resolve().parents[1] / "hooks" / "hooks.json").read_text(encoding="utf-8"))
    labels = [
        hook["statusMessage"]
        for entry in hooks["hooks"]["SubagentStop"]
        for hook in entry["hooks"]
    ]

    assert labels and all("census" not in label.lower() for label in labels)


def _linhas_de_comando(skill: str) -> list[list[str]]:
    """Cada trecho `harness4codex ...` da skill, com `<placeholder>` trocado por valor de exemplo."""
    texto = (ROOT / "skills" / skill / "SKILL.md").read_text(encoding="utf-8")
    exemplos = {"n": "3"}
    comandos = []
    for trecho in re.findall(r"`(harness4codex [^`]+)`", texto):
        trocado = re.sub(r"<([^>]+)>", lambda m: exemplos.get(m.group(1), "exemplo"), trecho)
        comandos.append(shlex.split(trocado)[1:])
    return comandos


def test_skills_nomeiam_comando_de_cli_que_o_parser_aceita():
    from harness4codex.cli import _build_parser

    parser = _build_parser()
    esperado = {"graph-context": {"graph"}, "assimilar": {"arsenal"}}

    for skill, grupos in esperado.items():
        comandos = _linhas_de_comando(skill)
        assert {c[0] for c in comandos} == grupos, skill
        for argv in comandos:
            args = parser.parse_args(argv)
            assert callable(args.func), (skill, argv)
    assert {c[1] for c in _linhas_de_comando("assimilar")} == {"check", "overlap"}

    # a metade que reprova: uma linha com flag que o parser nao conhece nao passa
    with pytest.raises(SystemExit):
        parser.parse_args(["graph", "context", "--repo", "r", "--task", "t", "--scope", "s", "--query", "q", "--inexistente", "x"])
