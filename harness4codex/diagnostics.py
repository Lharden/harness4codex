from __future__ import annotations

import os
import shutil
from collections.abc import Callable, Mapping
from dataclasses import asdict, dataclass
from pathlib import Path

import tomllib


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


def run_doctor(
    codex_home: str | Path,
    *,
    env: Mapping[str, str] | None = None,
    which: Callable[[str], str | None] = shutil.which,
    user_env: Mapping[str, str] | None = None,
) -> DoctorReport:
    home = Path(codex_home).expanduser().resolve()
    process_env = os.environ if env is None else env
    inherited_user_env = _windows_user_environment() if user_env is None else user_env
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
    harness4codex_enabled = any(
        name.split("@", 1)[0] == "harness4codex" and isinstance(value, dict) and value.get("enabled") is True
        for name, value in plugins.items()
    )
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

    return DoctorReport(
        ok=not any(check.status == "fail" for check in checks),
        codex_home=str(home),
        checks=tuple(checks),
    )
