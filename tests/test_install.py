import json
import shutil
import subprocess
from pathlib import Path

import pytest

from scripts.install import (
    _default_native_runner,
    _validate_active_plugin,
    build_hooks_config,
    ensure_feature_flag,
    install,
    native_plugin_enabled,
)


def test_native_runner_resolves_the_real_codex_launcher(monkeypatch, tmp_path):
    captured = {}
    launcher = str(tmp_path / "codex.CMD")
    monkeypatch.setattr(shutil, "which", lambda command: launcher if command == "codex" else None)

    def fake_run(command, **kwargs):
        captured["command"] = command
        captured["environment"] = kwargs["env"]
        return subprocess.CompletedProcess(command, 0, stdout="{}", stderr="")

    monkeypatch.setattr(subprocess, "run", fake_run)

    _default_native_runner(["codex", "plugin", "list"], tmp_path)

    assert captured["command"][0] == launcher
    assert captured["environment"]["CODEX_HOME"] == str(tmp_path)


def test_build_hooks_config_contains_all_core_events():
    config = build_hooks_config(r"C:\Users\me\.codex\plugins\harness4codex\hooks\codex_harness_hook.py")

    hooks = config["hooks"]
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
    (source / "hooks" / "hooks.json").write_text(json.dumps(build_hooks_config("hook.py")), encoding="utf-8")
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
    (source / "hooks" / "hooks.json").write_text(json.dumps(build_hooks_config("hook.py")), encoding="utf-8")
    (source / "hooks" / "codex_harness_hook.py").write_text("# hook\n", encoding="utf-8")
    (source / "skills" / "codex-harness-workflow").mkdir(parents=True)
    (source / "skills" / "codex-harness-workflow" / "SKILL.md").write_text("# skill\n", encoding="utf-8")
    codex_home = tmp_path / "codex"
    codex_home.mkdir()
    marketplace = tmp_path / "personal-marketplace"
    (codex_home / "config.toml").write_text(
        "[features]\nhooks = true\n"
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
    assert Path(result["active_plugin"]) == (codex_home / "plugins" / "cache" / "personal" / "harness4codex" / "2.0.0")


def test_install_bootstraps_native_marketplace_and_plugin_on_clean_home(tmp_path):
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
    (source / "harness4codex").mkdir()
    (source / "harness4codex" / "core.py").write_text("VALUE = 1\n", encoding="utf-8")
    (source / "skills" / "codex-harness-workflow").mkdir(parents=True)
    (source / "skills" / "codex-harness-workflow" / "SKILL.md").write_text(
        "# skill\n", encoding="utf-8"
    )
    codex_home = tmp_path / "codex"
    commands = []

    def native_runner(command, home):
        commands.append(command)
        if command[1:3] == ["plugin", "add"]:
            marketplace = home / "marketplaces" / "harness4codex-local"
            cached = home / "plugins" / "cache" / "harness4codex-local" / "harness4codex" / "2.0.0"
            shutil.copytree(marketplace / "plugins" / "harness4codex", cached)
        return subprocess.CompletedProcess(command, 0, stdout="{}", stderr="")

    result = install(source, codex_home, native_runner=native_runner)

    assert result["hook_mode"] == "plugin"
    assert commands == [
        ["codex", "plugin", "--help"],
        [
            "codex",
            "plugin",
            "marketplace",
            "add",
            str(codex_home / "marketplaces" / "harness4codex-local"),
            "--json",
        ],
        ["codex", "plugin", "add", "harness4codex@harness4codex-local", "--json"],
    ]
    config = (codex_home / "config.toml").read_text(encoding="utf-8")
    assert '[plugins."harness4codex@harness4codex-local"]' in config
    marketplace_manifest = json.loads(
        (
            codex_home
            / "marketplaces"
            / "harness4codex-local"
            / ".agents"
            / "plugins"
            / "marketplace.json"
        ).read_text(encoding="utf-8")
    )
    assert marketplace_manifest["plugins"][0]["source"]["path"] == "./plugins/harness4codex"


def test_active_plugin_validation_rejects_same_version_with_stale_core(tmp_path):
    source = tmp_path / "source"
    active = tmp_path / "active"
    for root in (source, active):
        (root / ".codex-plugin").mkdir(parents=True)
        (root / ".codex-plugin" / "plugin.json").write_text(
            json.dumps({"name": "harness4codex", "version": "2.0.0"}), encoding="utf-8"
        )
        (root / "hooks").mkdir()
        (root / "hooks" / "hooks.json").write_text("{}\n", encoding="utf-8")
        (root / "hooks" / "codex_harness_hook.py").write_text("# hook\n", encoding="utf-8")
        (root / "harness4codex").mkdir()
        (root / "harness4codex" / "core.py").write_text("VALUE = 1\n", encoding="utf-8")
    (active / "harness4codex" / "core.py").write_text("VALUE = 0\n", encoding="utf-8")

    with pytest.raises(RuntimeError, match="content fingerprint"):
        _validate_active_plugin(source, active)


def test_install_uses_global_hooks_when_native_plugin_is_not_enabled(tmp_path):
    source = tmp_path / "source"
    (source / "hooks").mkdir(parents=True)
    (source / "hooks" / "codex_harness_hook.py").write_text("# hook\n", encoding="utf-8")
    (source / "skills" / "codex-harness-workflow").mkdir(parents=True)
    (source / "skills" / "codex-harness-workflow" / "SKILL.md").write_text("# skill\n", encoding="utf-8")
    codex_home = tmp_path / "codex"

    def unsupported(command, _home):
        return subprocess.CompletedProcess(command, 2, stdout="", stderr="unknown command: plugin")

    result = install(source, codex_home, native_runner=unsupported)

    installed = json.loads((codex_home / "hooks.json").read_text(encoding="utf-8"))
    commands = [hook["command"] for entry in installed["hooks"]["Stop"] for hook in entry["hooks"]]
    assert result["hook_mode"] == "global"
    assert len([command for command in commands if "codex_harness_hook.py" in command]) == 1


def test_install_nao_copia_ambientes_virtuais(tmp_path):
    source = tmp_path / "source"
    (source / "hooks").mkdir(parents=True)
    (source / "hooks" / "codex_harness_hook.py").write_text("# hook\n", encoding="utf-8")
    (source / "skills" / "codex-harness-workflow").mkdir(parents=True)
    (source / "skills" / "codex-harness-workflow" / "SKILL.md").write_text("# skill\n", encoding="utf-8")
    for nome in (".venv", ".venv-ci"):
        (source / nome / "Scripts").mkdir(parents=True)
        (source / nome / "Scripts" / "python.exe").write_text("x", encoding="utf-8")
    codex_home = tmp_path / "codex"

    install(source, codex_home)

    plugin = codex_home / "plugins" / "harness4codex"
    assert (plugin / "hooks" / "codex_harness_hook.py").exists()
    assert not (plugin / ".venv").exists()
    assert not (plugin / ".venv-ci").exists()


# --- O-014: the install only runs from the published tree (clean checkout at origin/main) ------------------------
def _git(repo, *args):
    return subprocess.run(["git", "-c", "user.email=t@t", "-c", "user.name=t", *args], cwd=str(repo), check=True,
                          stdin=subprocess.DEVNULL, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                          text=True).stdout.strip()


def _published_source(tmp_path):
    remote, source = tmp_path / "remote.git", tmp_path / "source"
    subprocess.run(["git", "init", "-q", "--bare", str(remote)], check=True, stdin=subprocess.DEVNULL,
                   stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    source.mkdir()
    (source / "a.txt").write_text("a\n", encoding="utf-8")
    _git(source, "init", "-q", "-b", "main")
    _git(source, "add", "-A")
    _git(source, "commit", "-q", "-m", "base", "--no-verify")
    _git(source, "remote", "add", "origin", str(remote))
    _git(source, "push", "-q", "origin", "main")
    return source


@pytest.fixture
def installs(monkeypatch):
    import scripts.install as module

    calls = []
    monkeypatch.setattr(module, "install", lambda source, home, dry=False: calls.append(source) or {"ok": "1"})
    return module, calls


def test_published_source_installs(tmp_path, installs):
    module, calls = installs
    source = _published_source(tmp_path)

    assert module.unpublished_source_reason(source) == ""
    assert module.main(["--source", str(source), "--codex-home", str(tmp_path / "home")]) == 0
    assert calls == [source]


@pytest.mark.parametrize("damage", ["modified", "untracked", "unpublished_commit", "no_remote", "archive"])
def test_unpublished_source_is_refused_before_copying(tmp_path, installs, capsys, damage):
    module, calls = installs
    source = _published_source(tmp_path)
    if damage == "modified":
        (source / "a.txt").write_text("changed\n", encoding="utf-8")
    elif damage == "untracked":
        (source / "new.txt").write_text("x\n", encoding="utf-8")
    elif damage == "unpublished_commit":
        (source / "a.txt").write_text("local\n", encoding="utf-8")
        _git(source, "commit", "-q", "-am", "local", "--no-verify")
    elif damage == "no_remote":
        _git(source, "remote", "remove", "origin")
    else:  # the 2026-10-14 case: an archive of an old tree, not a checkout
        source = tmp_path / "archive"
        source.mkdir()
        (source / "a.txt").write_text("old\n", encoding="utf-8")

    assert module.main(["--source", str(source), "--codex-home", str(tmp_path / "home")]) == 2
    assert calls == []
    assert "install refused" in capsys.readouterr().err
    assert not (tmp_path / "home").exists()


def test_forced_install_runs_and_is_recorded(tmp_path, installs):
    module, calls = installs
    source = _published_source(tmp_path)
    (source / "a.txt").write_text("hotfix\n", encoding="utf-8")
    home = tmp_path / "home"

    assert module.main(["--source", str(source), "--codex-home", str(home), "--force-unpublished", "hotfix"]) == 0

    assert calls == [source]
    entry = json.loads((home / "harness4codex" / "install-forced.jsonl").read_text(encoding="utf-8").splitlines()[-1])
    assert entry["reason"] == "hotfix" and "uncommitted" in entry["problem"]


def test_forced_install_without_reason_is_refused(tmp_path, installs):
    module, calls = installs
    source = _published_source(tmp_path)
    (source / "a.txt").write_text("x\n", encoding="utf-8")

    assert module.main(["--source", str(source), "--codex-home", str(tmp_path / "h"), "--force-unpublished", " "]) == 2
    assert calls == []


def test_dry_run_does_not_check_the_source(tmp_path, installs):
    """The dry run writes nothing, so it plans from any tree (the check guards writes)."""
    module, calls = installs
    plain = tmp_path / "plain"
    plain.mkdir()

    assert module.main(["--source", str(plain), "--codex-home", str(tmp_path / "h"), "--dry-run"]) == 0
    assert calls == [plain]
