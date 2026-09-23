import json
import os
import sqlite3
import time

from harness4codex.diagnostics import run_doctor

REQUIRED_HOOKS = {
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
}


def _write_config(home, text):
    home.mkdir(parents=True, exist_ok=True)
    marketplace = home / "marketplace"
    source = marketplace / "plugins" / "harness4codex"
    active = home / "plugins" / "cache" / "personal" / "harness4codex" / "1.1.0"
    for plugin in (source, active):
        (plugin / ".codex-plugin").mkdir(parents=True)
        (plugin / ".codex-plugin" / "plugin.json").write_text(
            json.dumps({"name": "harness4codex", "version": "1.1.0"}), encoding="utf-8"
        )
        (plugin / "hooks").mkdir()
        (plugin / "hooks" / "hooks.json").write_text(
            json.dumps(
                {
                    "hooks": {
                        event: [
                            {
                                "hooks": [
                                    {
                                        "type": "command",
                                        "command": "python hooks/codex_harness_hook.py",
                                    }
                                ]
                            }
                        ]
                        for event in REQUIRED_HOOKS
                    }
                }
            ),
            encoding="utf-8",
        )
        (plugin / "hooks" / "codex_harness_hook.py").write_text("# hook\n", encoding="utf-8")
    marketplace_config = f'\n[marketplaces.personal]\nsource_type = "local"\nsource = "{marketplace.as_posix()}"\n'
    (home / "config.toml").write_text(text + marketplace_config, encoding="utf-8")


def test_doctor_detects_competing_supervisor_and_disabled_required_apps(tmp_path):
    _write_config(
        tmp_path,
        """
[features]
hooks = true
enable_mcp_apps = false

[plugins."harness4codex@personal"]
enabled = true

[plugins."harness4claude@harness4claude"]
enabled = true
""",
    )

    report = run_doctor(tmp_path, env={}, which=lambda _name: None, user_env={})

    assert report.ok is False
    codes = {check.code for check in report.checks if check.status == "fail"}
    assert "MULTIPLE_SUPERVISORS" in codes
    assert "CODEX_APPS_REQUIRED" in codes


def test_doctor_accepts_one_supervisor_obsidian_and_science_mcp(tmp_path):
    _write_config(
        tmp_path,
        """
[features]
hooks = true
enable_mcp_apps = true

[plugins."harness4codex@personal"]
enabled = true

[plugins."harness4claude@harness4claude"]
enabled = false

[mcp_servers.obsidian]
url = "https://127.0.0.1:27124/mcp/"
bearer_token_env_var = "OBSIDIAN_API_KEY"

[mcp_servers.science_harness]
command = "shs"
args = ["claims-mcp"]
""",
    )

    report = run_doctor(
        tmp_path,
        env={"OBSIDIAN_API_KEY": "secret", "HARNESS_CONTROL_TOKEN": "lite-token"},
        which=lambda name: r"C:\bin\shs.exe" if name == "shs" else None,
        user_env={},
    )

    assert report.ok is True
    assert not [check for check in report.checks if check.status == "fail"]
    codes = {check.code for check in report.checks}
    assert "CONTRACT_LOCK_VALID" in codes
    assert "FULL_LIFECYCLE_HOOKS" in codes



def test_doctor_aceita_a_forma_que_a_producao_usa_env_vars(tmp_path):
    """O ~/.codex/config.toml REAL nao tem `bearer_token_env_var`.

    Medido em 2026-09-07: a chave aparece neste arquivo em oito lugares e em
    NENHUM dos cinco servidores do config de producao. O obsidian de verdade
    declara `env_vars = ["OBSIDIAN_API_KEY"]` e injeta o token no header dos
    `args`. O resultado eram 175 testes verdes e o doctor reprovando uma
    maquina configurada certo, com OBSIDIAN_TOKEN_MISSING, desde sempre.

    Mesmo defeito que fez a presenca do harness4claude nunca funcionar em
    producao enquanto a suite dela era verde: a suite media uma condicao que
    a producao nao tem.
    """
    _write_config(
        tmp_path,
        """
[features]
hooks = true
enable_mcp_apps = true

[plugins."harness4codex@personal"]
enabled = true

[plugins."harness4claude@harness4claude"]
enabled = false

[mcp_servers.obsidian]
command = "npx"
args = ["-y", "mcp-remote", "https://127.0.0.1:27124/mcp/", "--header", "Authorization:Bearer ${OBSIDIAN_API_KEY}"]
env_vars = ["OBSIDIAN_API_KEY"]

[mcp_servers.science_harness]
command = "shs"
args = ["claims-mcp"]
""",
    )

    report = run_doctor(
        tmp_path,
        env={"OBSIDIAN_API_KEY": "secret", "HARNESS_CONTROL_TOKEN": "lite-token"},
        which=lambda name: r"C:\bin\shs.exe" if name == "shs" else None,
        user_env={},
    )

    assert report.ok is True
    assert not [check for check in report.checks if check.status == "fail"]
    codes = {check.code for check in report.checks}
    assert "OBSIDIAN_READY" in codes, "a forma de producao tem de passar"
    assert "OBSIDIAN_TOKEN_MISSING" not in codes


def test_doctor_marks_obsidian_restart_when_user_env_has_token_but_process_does_not(tmp_path):
    _write_config(
        tmp_path,
        """
[features]
hooks = true
enable_mcp_apps = true
[plugins."harness4codex@personal"]
enabled = true
[mcp_servers.obsidian]
url = "https://127.0.0.1:27124/mcp/"
bearer_token_env_var = "OBSIDIAN_API_KEY"
[mcp_servers.science_harness]
command = "shs"
args = ["claims-mcp"]
""",
    )

    report = run_doctor(
        tmp_path,
        env={},
        which=lambda name: r"C:\bin\shs.exe" if name == "shs" else None,
        user_env={"OBSIDIAN_API_KEY": "secret", "HARNESS_CONTROL_TOKEN": "lite-token"},
    )

    check = next(item for item in report.checks if item.code == "OBSIDIAN_RESTART_REQUIRED")
    assert check.status == "warn"
    lite = next(item for item in report.checks if item.code == "HARNESS_LITE_RESTART_REQUIRED")
    assert lite.status == "warn"


def test_doctor_fails_when_active_plugin_is_older_than_marketplace_source(tmp_path):
    _write_config(
        tmp_path,
        """
[features]
hooks = true
enable_mcp_apps = true
[plugins."harness4codex@personal"]
enabled = true
[mcp_servers.obsidian]
url = "https://127.0.0.1:27124/mcp/"
bearer_token_env_var = "OBSIDIAN_API_KEY"
[mcp_servers.science_harness]
command = "shs"
args = ["claims-mcp"]
""",
    )
    stale = tmp_path / "plugins" / "cache" / "personal" / "harness4codex" / "1.1.0"
    stale_manifest = stale / ".codex-plugin" / "plugin.json"
    stale_manifest.write_text(json.dumps({"name": "harness4codex", "version": "0.4.0"}), encoding="utf-8")

    report = run_doctor(
        tmp_path,
        env={"OBSIDIAN_API_KEY": "secret", "HARNESS_CONTROL_TOKEN": "token"},
        which=lambda name: "shs" if name == "shs" else None,
        user_env={},
    )

    stale_check = next(check for check in report.checks if check.code == "ACTIVE_PLUGIN_STALE")
    assert stale_check.status == "fail"
    assert "0.4.0" in stale_check.message and "1.1.0" in stale_check.message


def test_doctor_rejects_same_version_active_cache_with_different_core(tmp_path):
    _write_config(
        tmp_path,
        """
[features]
hooks = true
enable_mcp_apps = true
[plugins."harness4codex@personal"]
enabled = true
[mcp_servers.obsidian]
bearer_token_env_var = "OBSIDIAN_API_KEY"
[mcp_servers.science_harness]
command = "shs"
args = ["claims-mcp"]
""",
    )
    source = tmp_path / "marketplace" / "plugins" / "harness4codex"
    active = tmp_path / "plugins" / "cache" / "personal" / "harness4codex" / "1.1.0"
    for root, value in ((source, 1), (active, 0)):
        (root / "harness4codex").mkdir()
        (root / "harness4codex" / "core.py").write_text(
            f"VALUE = {value}\n", encoding="utf-8"
        )

    report = run_doctor(
        tmp_path,
        env={"OBSIDIAN_API_KEY": "secret", "HARNESS_CONTROL_TOKEN": "token"},
        which=lambda name: "shs" if name == "shs" else None,
        user_env={},
    )

    check = next(item for item in report.checks if item.code == "ACTIVE_PLUGIN_CONTENT_MISMATCH")
    assert check.status == "fail"


def test_doctor_rejects_registered_events_without_handlers(tmp_path):
    _write_config(
        tmp_path,
        """
[features]
hooks = true
enable_mcp_apps = true
[plugins."harness4codex@personal"]
enabled = true
[mcp_servers.obsidian]
bearer_token_env_var = "OBSIDIAN_API_KEY"
[mcp_servers.science_harness]
command = "shs"
args = ["claims-mcp"]
""",
    )
    source = tmp_path / "marketplace" / "plugins" / "harness4codex"
    active = tmp_path / "plugins" / "cache" / "personal" / "harness4codex" / "1.1.0"
    empty = json.dumps({"hooks": {event: [] for event in REQUIRED_HOOKS}})
    for root in (source, active):
        (root / "hooks" / "hooks.json").write_text(empty, encoding="utf-8")

    report = run_doctor(
        tmp_path,
        env={"OBSIDIAN_API_KEY": "secret", "HARNESS_CONTROL_TOKEN": "token"},
        which=lambda name: "shs" if name == "shs" else None,
        user_env={},
    )

    check = next(item for item in report.checks if item.code == "FULL_LIFECYCLE_HOOKS")
    assert check.status == "fail"
    assert "without command handlers" in check.message


def test_doctor_rejects_handlers_whose_runtime_wrapper_is_missing(tmp_path):
    _write_config(
        tmp_path,
        """
[features]
hooks = true
enable_mcp_apps = true
[plugins."harness4codex@personal"]
enabled = true
[mcp_servers.obsidian]
bearer_token_env_var = "OBSIDIAN_API_KEY"
[mcp_servers.science_harness]
command = "shs"
args = ["claims-mcp"]
""",
    )
    source = tmp_path / "marketplace" / "plugins" / "harness4codex"
    active = tmp_path / "plugins" / "cache" / "personal" / "harness4codex" / "1.1.0"
    for root in (source, active):
        (root / "hooks" / "codex_harness_hook.py").unlink()

    report = run_doctor(
        tmp_path,
        env={"OBSIDIAN_API_KEY": "secret", "HARNESS_CONTROL_TOKEN": "token"},
        which=lambda name: "shs" if name == "shs" else None,
        user_env={},
    )

    check = next(item for item in report.checks if item.code == "FULL_LIFECYCLE_HOOKS")
    assert check.status == "fail"
    assert "runtime wrapper" in check.message


def test_doctor_fails_when_configured_marketplace_lags_inspected_source(tmp_path):
    _write_config(
        tmp_path,
        """
[features]
hooks = true
enable_mcp_apps = true
[plugins."harness4codex@personal"]
enabled = true
[mcp_servers.obsidian]
bearer_token_env_var = "OBSIDIAN_API_KEY"
[mcp_servers.science_harness]
command = "shs"
args = ["claims-mcp"]
""",
    )
    source_manifest = tmp_path / "marketplace" / "plugins" / "harness4codex" / ".codex-plugin" / "plugin.json"
    source_manifest.write_text(json.dumps({"name": "harness4codex", "version": "0.9.0"}), encoding="utf-8")

    report = run_doctor(
        tmp_path,
        env={"OBSIDIAN_API_KEY": "secret", "HARNESS_CONTROL_TOKEN": "token"},
        which=lambda name: "shs" if name == "shs" else None,
        user_env={},
    )

    check = next(check for check in report.checks if check.code == "MARKETPLACE_SOURCE_STALE")
    assert check.status == "fail"
    assert "0.9.0" in check.message and "1.1.0" in check.message


def test_doctor_enumerates_scoped_state_databases(tmp_path):
    _write_config(
        tmp_path,
        """
[features]
hooks = true
enable_mcp_apps = true
[plugins."harness4codex@personal"]
enabled = true
[mcp_servers.obsidian]
bearer_token_env_var = "OBSIDIAN_API_KEY"
[mcp_servers.science_harness]
command = "shs"
args = ["claims-mcp"]
""",
    )
    first = tmp_path / "harness" / "projects" / "one" / "sessions" / "a" / "harness.db"
    second = tmp_path / "harness" / "projects" / "two" / "sessions" / "b" / "harness.db"
    for database in (first, second):
        database.parent.mkdir(parents=True)
        connection = sqlite3.connect(database)
        try:
            connection.execute("CREATE TABLE health (ok INTEGER)")
            connection.commit()
        finally:
            connection.close()

    report = run_doctor(
        tmp_path,
        env={"OBSIDIAN_API_KEY": "secret", "HARNESS_CONTROL_TOKEN": "token"},
        which=lambda name: "shs" if name == "shs" else None,
        user_env={},
    )

    state_check = next(check for check in report.checks if check.code == "SCOPED_STATE_DATABASES")
    assert state_check.status == "pass"
    assert "2" in state_check.message


HEALTHY_CONFIG = """
[features]
hooks = true
enable_mcp_apps = true
[plugins."harness4codex@personal"]
enabled = true
[mcp_servers.obsidian]
bearer_token_env_var = "OBSIDIAN_API_KEY"
[mcp_servers.science_harness]
command = "shs"
args = ["claims-mcp"]
"""


def _doctor(home, now=None):
    return run_doctor(
        home,
        env={"OBSIDIAN_API_KEY": "secret", "HARNESS_CONTROL_TOKEN": "token"},
        which=lambda name: "shs" if name == "shs" else None,
        user_env={},
        now=now,
    )


def _check(report, code):
    return next(check for check in report.checks if check.code == code)


def _installed_at(home, moment):
    active_hooks = home / "plugins" / "cache" / "personal" / "harness4codex" / "1.1.0" / "hooks" / "hooks.json"
    os.utime(active_hooks, (moment, moment))


def _write_rollout(home, started_at, *, source="exec", originator="codex_exec", name="a"):
    path = home / "sessions" / "2026" / "09" / "23" / f"rollout-{name}.jsonl"
    path.parent.mkdir(parents=True, exist_ok=True)
    lines = [
        {"type": "session_meta", "payload": {"source": source, "originator": originator}},
        {"type": "event_msg", "payload": {"type": "task_started", "started_at": int(started_at)}},
    ]
    path.write_text("\n".join(json.dumps(line) for line in lines) + "\n", encoding="utf-8")
    os.utime(path, (started_at + 30, started_at + 30))


def _write_heartbeat(home, moment, event="UserPromptSubmit"):
    beat = home / "harness" / "heartbeats" / event
    beat.parent.mkdir(parents=True, exist_ok=True)
    beat.write_text(str(moment), encoding="utf-8")


def test_doctor_rejects_cmd_style_variables_in_hook_commands(tmp_path):
    """B-18: `%PLUGIN_ROOT%` chega literal ao PowerShell em que o Codex roda o hook."""
    _write_config(tmp_path, HEALTHY_CONFIG)
    active = tmp_path / "plugins" / "cache" / "personal" / "harness4codex" / "1.1.0"
    broken = {
        "type": "command",
        "command": 'python "${PLUGIN_ROOT}/hooks/codex_harness_hook.py"',
        "commandWindows": 'python "%PLUGIN_ROOT%\\hooks\\codex_harness_hook.py"',
    }
    (active / "hooks" / "hooks.json").write_text(
        json.dumps({"hooks": {event: [{"hooks": [broken]}] for event in REQUIRED_HOOKS}}), encoding="utf-8"
    )

    check = _check(_doctor(tmp_path), "HOOK_COMMAND_NOT_PORTABLE")

    assert check.status == "fail"
    assert "%PLUGIN_ROOT%" in check.message


def test_doctor_fails_when_cli_turns_ran_since_install_and_hook_never_fired(tmp_path):
    """O caso exato do B-18: o Codex abriu turnos e o hook nunca deixou rastro."""
    now = time.time()
    _write_config(tmp_path, HEALTHY_CONFIG)
    _installed_at(tmp_path, now - 3 * 3600)
    _write_rollout(tmp_path, now - 3600)

    report = _doctor(tmp_path, now=now)

    check = _check(report, "HOOK_INACTIVE")
    assert check.status == "fail"
    assert report.ok is False


def test_doctor_fails_when_cli_turns_are_newer_than_the_last_heartbeat(tmp_path):
    now = time.time()
    _write_config(tmp_path, HEALTHY_CONFIG)
    _write_heartbeat(tmp_path, now - 5 * 3600)
    _write_rollout(tmp_path, now - 3600)

    assert _check(_doctor(tmp_path, now=now), "HOOK_INACTIVE").status == "fail"


def test_doctor_reports_the_hook_active_when_heartbeat_follows_the_turn(tmp_path):
    now = time.time()
    _write_config(tmp_path, HEALTHY_CONFIG)
    _write_rollout(tmp_path, now - 3600)
    _write_heartbeat(tmp_path, now - 3600 + 10)

    check = _check(_doctor(tmp_path, now=now), "HOOK_ACTIVE")

    assert check.status == "pass"


def test_doctor_does_not_judge_desktop_or_subagent_turns(tmp_path):
    """Medido em 2026-09-23: 492 rollouts do Desktop sem injecao de harness nenhum.

    Sao jobs programaticos em que nenhum hook dispara, entao nao autorizam
    veredito. Sem observacao assertivel o resultado e nao verificado (L-09).
    """
    now = time.time()
    _write_config(tmp_path, HEALTHY_CONFIG)
    _installed_at(tmp_path, now - 3 * 3600)
    _write_rollout(tmp_path, now - 3600, source="vscode", originator="Codex Desktop", name="desktop")
    _write_rollout(
        tmp_path, now - 3600, source={"subagent": {"other": "guardian"}}, originator="codex-tui", name="sub"
    )

    report = _doctor(tmp_path, now=now)

    check = _check(report, "HOOK_ACTIVITY_NOT_VERIFIED")
    assert check.status == "warn"
    assert "HOOK_INACTIVE" not in {item.code for item in report.checks}


def test_doctor_reports_activity_not_verified_without_any_observation(tmp_path):
    _write_config(tmp_path, HEALTHY_CONFIG)

    report = _doctor(tmp_path)

    assert _check(report, "HOOK_ACTIVITY_NOT_VERIFIED").status == "warn"
    assert report.ok is True
