from __future__ import annotations

import json
import os
import shutil
import sqlite3
from collections.abc import Callable, Mapping
from dataclasses import asdict, dataclass
from pathlib import Path

try:
    import tomllib
except ModuleNotFoundError:  # pragma: no cover - exercised by the Python 3.10 CI job
    import tomli as tomllib

from .contract import ContractSnapshot

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


@dataclass(frozen=True)
class DiagnosticCheck:
    code: str
    status: str
    message: str


@dataclass(frozen=True)
class DoctorReport:
    ok: bool
    codex_home: str
    checks: tuple[DiagnosticCheck, ...]

    def to_dict(self) -> dict[str, object]:
        return {"ok": self.ok, "codex_home": self.codex_home, "checks": [asdict(check) for check in self.checks]}


def _windows_user_environment() -> dict[str, str]:
    if os.name != "nt":
        return {}
    try:
        import winreg

        values: dict[str, str] = {}
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, "Environment") as key:
            index = 0
            while True:
                try:
                    name, value, _kind = winreg.EnumValue(key, index)
                except OSError:
                    break
                values[str(name)] = str(value)
                index += 1
        return values
    except OSError:
        return {}


def _load_config(path: Path) -> tuple[dict, DiagnosticCheck | None]:
    if not path.exists():
        return {}, DiagnosticCheck("CONFIG_MISSING", "fail", f"Codex config not found: {path}")
    try:
        with path.open("rb") as handle:
            return tomllib.load(handle), None
    except (OSError, tomllib.TOMLDecodeError) as exc:
        return {}, DiagnosticCheck("CONFIG_INVALID", "fail", f"Could not parse {path}: {exc}")


def _read_plugin_manifest(plugin_root: Path) -> dict | None:
    try:
        payload = json.loads((plugin_root / ".codex-plugin" / "plugin.json").read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    return payload if isinstance(payload, dict) else None


def _marketplace_plugin(config: dict, selector: str) -> Path | None:
    if "@" not in selector:
        return None
    marketplace_name = selector.split("@", 1)[1]
    marketplaces = config.get("marketplaces") if isinstance(config.get("marketplaces"), dict) else {}
    marketplace = marketplaces.get(marketplace_name)
    if not isinstance(marketplace, dict) or marketplace.get("source_type") != "local":
        return None
    source = marketplace.get("source")
    if not isinstance(source, str) or not source.strip():
        return None
    return Path(source) / "plugins" / "harness4codex"


def _active_plugin(home: Path, selector: str, expected_version: str | None) -> Path | None:
    marketplace_name = selector.split("@", 1)[1] if "@" in selector else ""
    cache = home / "plugins" / "cache" / marketplace_name / "harness4codex"
    if expected_version and (cache / expected_version).is_dir():
        return cache / expected_version
    candidates = [path for path in cache.iterdir() if path.is_dir()] if cache.is_dir() else []
    return max(candidates, key=lambda path: path.stat().st_mtime_ns) if candidates else None


def _registered_hooks(plugin_root: Path) -> set[str]:
    try:
        payload = json.loads((plugin_root / "hooks" / "hooks.json").read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return set()
    hooks = payload.get("hooks") if isinstance(payload, dict) else None
    return set(hooks) if isinstance(hooks, dict) else set()


def _state_database_checks(home: Path) -> list[DiagnosticCheck]:
    databases = set((home / "harness").rglob("harness.db")) if (home / "harness").is_dir() else set()
    if (home / "harness.db").is_file():
        databases.add(home / "harness.db")
    failures: list[str] = []
    for database in sorted(databases):
        connection: sqlite3.Connection | None = None
        try:
            connection = sqlite3.connect(database)
            integrity = connection.execute("PRAGMA integrity_check").fetchone()[0]
            if integrity != "ok":
                failures.append(f"{database}: {integrity}")
        except sqlite3.Error as exc:
            failures.append(f"{database}: {exc}")
        finally:
            if connection is not None:
                connection.close()
    if failures:
        return [
            DiagnosticCheck(
                "SCOPED_STATE_DATABASES",
                "fail",
                f"Checked {len(databases)} scoped state database(s); failures: " + "; ".join(failures),
            )
        ]
    return [
        DiagnosticCheck(
            "SCOPED_STATE_DATABASES",
            "pass" if databases else "warn",
            f"Checked {len(databases)} scoped state database(s); all are healthy.",
        )
    ]


def run_doctor(
    codex_home: str | Path,
    *,
    env: Mapping[str, str] | None = None,
    which: Callable[[str], str | None] = shutil.which,
    user_env: Mapping[str, str] | None = None,
    source_root: str | Path | None = None,
) -> DoctorReport:
    home = Path(codex_home).expanduser().resolve()
    process_env = os.environ if env is None else env
    inherited_user_env = _windows_user_environment() if user_env is None else user_env
    runtime_source = Path(source_root or Path(__file__).resolve().parents[1]).resolve()
    runtime_manifest = _read_plugin_manifest(runtime_source)
    config, config_error = _load_config(home / "config.toml")
    checks: list[DiagnosticCheck] = []
    if config_error is not None:
        checks.append(config_error)

    features = config.get("features") if isinstance(config.get("features"), dict) else {}
    if features.get("hooks") is True:
        checks.append(DiagnosticCheck("HOOKS_ENABLED", "pass", "Codex hooks are enabled."))
    else:
        checks.append(DiagnosticCheck("HOOKS_DISABLED", "fail", "Set features.hooks = true."))

    plugins = config.get("plugins") if isinstance(config.get("plugins"), dict) else {}
    harness_selectors = [
        name
        for name, value in plugins.items()
        if name.split("@", 1)[0] == "harness4codex"
        and isinstance(value, dict)
        and value.get("enabled") is True
    ]
    harness4codex_enabled = bool(harness_selectors)
    competing = [
        name
        for name, value in plugins.items()
        if name.split("@", 1)[0] == "harness4claude" and isinstance(value, dict) and value.get("enabled") is True
    ]
    if not harness4codex_enabled:
        checks.append(
            DiagnosticCheck("HARNESS4CODEX_PLUGIN_DISABLED", "fail", "Enable the Harness4Codex plugin for this host.")
        )
    if competing:
        checks.append(
            DiagnosticCheck(
                "MULTIPLE_SUPERVISORS",
                "fail",
                "More than one workflow supervisor is enabled for Codex: " + ", ".join(competing),
            )
        )
    else:
        checks.append(DiagnosticCheck("SINGLE_SUPERVISOR", "pass", "Harness4Codex is the Codex workflow supervisor."))

    active_plugin: Path | None = None
    expected_plugin: Path | None = None
    if harness_selectors:
        selector = harness_selectors[0]
        expected_plugin = _marketplace_plugin(config, selector)
        expected_manifest = _read_plugin_manifest(expected_plugin) if expected_plugin else None
        expected_version = str(expected_manifest.get("version")) if expected_manifest else None
        active_plugin = _active_plugin(home, selector, expected_version)
        active_manifest = _read_plugin_manifest(active_plugin) if active_plugin else None
        if expected_plugin is None or expected_manifest is None:
            checks.append(
                DiagnosticCheck(
                    "MARKETPLACE_SOURCE_INVALID",
                    "fail",
                    f"Could not resolve a valid local marketplace source for {selector}.",
                )
            )
        elif runtime_manifest and runtime_manifest.get("version") != expected_version:
            checks.append(
                DiagnosticCheck(
                    "MARKETPLACE_SOURCE_STALE",
                    "fail",
                    f"Configured marketplace has Harness4Codex {expected_version}; "
                    f"the inspected source is {runtime_manifest.get('version')}.",
                )
            )
        elif active_plugin is None or active_manifest is None:
            checks.append(
                DiagnosticCheck("ACTIVE_PLUGIN_MISSING", "fail", f"No active cache entry exists for {selector}.")
            )
        elif active_manifest.get("version") != expected_version:
            checks.append(
                DiagnosticCheck(
                    "ACTIVE_PLUGIN_STALE",
                    "fail",
                    f"Active Harness4Codex is {active_manifest.get('version')}; marketplace source is {expected_version}.",
                )
            )
        else:
            checks.append(
                DiagnosticCheck(
                    "ACTIVE_PLUGIN_CURRENT",
                    "pass",
                    f"Active Harness4Codex {expected_version} matches {expected_plugin}.",
                )
            )

    if features.get("enable_mcp_apps") is True:
        checks.append(DiagnosticCheck("CODEX_APPS_ENABLED", "pass", "Codex Apps startup is required."))
    else:
        checks.append(
            DiagnosticCheck(
                "CODEX_APPS_REQUIRED",
                "fail",
                "Codex Apps is required but features.enable_mcp_apps is not enabled.",
            )
        )

    servers = config.get("mcp_servers") if isinstance(config.get("mcp_servers"), dict) else {}
    obsidian = servers.get("obsidian") if isinstance(servers.get("obsidian"), dict) else None
    if obsidian is None:
        checks.append(DiagnosticCheck("OBSIDIAN_MCP_MISSING", "fail", "The obsidian MCP server is not configured."))
    else:
        token_name = str(obsidian.get("bearer_token_env_var") or "")
        if token_name and process_env.get(token_name):
            checks.append(DiagnosticCheck("OBSIDIAN_READY", "pass", "Obsidian MCP token is visible to this process."))
        elif token_name and inherited_user_env.get(token_name):
            checks.append(
                DiagnosticCheck(
                    "OBSIDIAN_RESTART_REQUIRED",
                    "warn",
                    f"{token_name} exists in the user environment; restart Codex so it inherits the token.",
                )
            )
        else:
            checks.append(
                DiagnosticCheck(
                    "OBSIDIAN_TOKEN_MISSING",
                    "fail",
                    "The configured Obsidian bearer token environment variable is unavailable.",
                )
            )

    science = servers.get("science_harness") if isinstance(servers.get("science_harness"), dict) else None
    if science is None:
        checks.append(
            DiagnosticCheck("SCIENCE_MCP_MISSING", "fail", "Register the science_harness MCP server with `shs claims-mcp`.")
        )
    else:
        command = str(science.get("command") or "")
        args = science.get("args") if isinstance(science.get("args"), list) else []
        executable = str(Path(command).resolve()) if command and Path(command).is_absolute() and Path(command).exists() else which(command)
        if executable and "claims-mcp" in args:
            checks.append(DiagnosticCheck("SCIENCE_MCP_READY", "pass", "Science Harness MCP is registered read-only."))
        else:
            checks.append(
                DiagnosticCheck("SCIENCE_MCP_INVALID", "fail", "science_harness must run an available `shs claims-mcp` command.")
            )

    if process_env.get("HARNESS_CONTROL_TOKEN"):
        checks.append(DiagnosticCheck("HARNESS_LITE_PREVIEW_READY", "pass", "Harness Lite preview is configured."))
    elif inherited_user_env.get("HARNESS_CONTROL_TOKEN"):
        checks.append(
            DiagnosticCheck(
                "HARNESS_LITE_RESTART_REQUIRED",
                "warn",
                "HARNESS_CONTROL_TOKEN exists in the user environment; restart Codex so hooks inherit it.",
            )
        )
    else:
        checks.append(
            DiagnosticCheck(
                "HARNESS_LITE_PREVIEW_UNCONFIGURED",
                "warn",
                "Set HARNESS_CONTROL_TOKEN to activate automatic advisory previews.",
            )
        )

    lite_home_value = process_env.get("HARNESS_HOME") or inherited_user_env.get("HARNESS_HOME")
    if lite_home_value and not (Path(lite_home_value).expanduser() / "control-plane.json").exists():
        checks.append(
            DiagnosticCheck(
                "HARNESS_LITE_HOME_UNINITIALIZED",
                "warn",
                "Harness Lite has credentials but its control-plane home has not been initialised.",
            )
        )

    legacy_hooks = home / "hooks.json"
    if legacy_hooks.exists():
        try:
            legacy_text = legacy_hooks.read_text(encoding="utf-8")
        except OSError:
            legacy_text = ""
        if "codex_harness_hook.py" in legacy_text and harness4codex_enabled:
            checks.append(
                DiagnosticCheck(
                    "DUPLICATE_HOOK_REGISTRATION",
                    "fail",
                    "Harness4Codex is registered by both the plugin and the global hooks file.",
                )
            )

    snapshot = ContractSnapshot.load()
    if snapshot.verify_lock():
        checks.append(DiagnosticCheck("CONTRACT_LOCK_VALID", "pass", f"Harness4Contract {snapshot.version} lock is valid."))
    else:
        checks.append(DiagnosticCheck("CONTRACT_LOCK_INVALID", "fail", "Vendored Harness4Contract snapshot does not match its lock."))

    inspected_plugin = active_plugin or expected_plugin or Path(__file__).resolve().parents[1]
    registered = _registered_hooks(inspected_plugin)
    missing_hooks = sorted(REQUIRED_HOOKS - registered)
    if missing_hooks:
        checks.append(
            DiagnosticCheck(
                "LIFECYCLE_HOOKS_INCOMPLETE",
                "fail",
                f"Active plugin is missing lifecycle hooks: {missing_hooks}",
            )
        )
    else:
        checks.append(DiagnosticCheck("FULL_LIFECYCLE_HOOKS", "pass", "All Codex lifecycle hooks are registered."))

    checks.extend(_state_database_checks(home))

    return DoctorReport(
        ok=not any(check.status == "fail" for check in checks),
        codex_home=str(home),
        checks=tuple(checks),
    )
