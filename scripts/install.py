from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import subprocess
import uuid
from collections.abc import Callable
from pathlib import Path
from typing import Any

EVENTS = [
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
]


def _quote_path(path: str | os.PathLike[str]) -> str:
    return '"' + str(path).replace('"', '\\"') + '"'


def _hook_entry(hook_path: str | os.PathLike[str], status: str, matcher: str | None = None) -> dict[str, Any]:
    entry: dict[str, Any] = {
        "hooks": [
            {
                "type": "command",
                "command": f"python {_quote_path(hook_path)}",
                "statusMessage": status,
            }
        ]
    }
    if matcher is not None:
        entry["matcher"] = matcher
    return entry


def build_hooks_config(hook_path: str | os.PathLike[str]) -> dict[str, Any]:
    return {
        "hooks": {
            "SessionStart": [_hook_entry(hook_path, "Harness4Codex session", "startup|resume|clear")],
            "UserPromptSubmit": [_hook_entry(hook_path, "Harness4Codex classify")],
            "PreToolUse": [_hook_entry(hook_path, "Harness4Codex guard", "Bash|shell_command|exec_command|functions.exec|functions.exec_command|apply_patch")],
            "PermissionRequest": [_hook_entry(hook_path, "Harness4Codex permission", "Bash|shell_command|exec_command|functions.exec|functions.exec_command")],
            "PostToolUse": [_hook_entry(hook_path, "Harness4Codex state", "Bash|shell_command|exec_command|functions.exec|functions.exec_command|apply_patch")],
            "PreCompact": [_hook_entry(hook_path, "Harness4Codex handoff")],
            "PostCompact": [_hook_entry(hook_path, "Harness4Codex restore")],
            "SubagentStart": [_hook_entry(hook_path, "Harness4Codex node start")],
            "SubagentStop": [_hook_entry(hook_path, "Harness4Codex node result")],
            "Stop": [_hook_entry(hook_path, "Harness4Codex verify")],
            "SessionEnd": [_hook_entry(hook_path, "Harness4Codex session close")],
        }
    }


def ensure_feature_flag(text: str) -> str:
    lines = [line for line in text.splitlines() if not re.match(r"\s*codex_hooks\s*=", line)]
    if not lines:
        return "[features]\nhooks = true\n"

    features_start = None
    next_section = len(lines)
    for index, line in enumerate(lines):
        if re.match(r"\s*\[features\]\s*$", line):
            features_start = index
            continue
        if features_start is not None and index > features_start and re.match(r"\s*\[.+\]\s*$", line):
            next_section = index
            break

    if features_start is None:
        suffix = "" if text.endswith("\n") else "\n"
        return "\n".join(lines) + suffix + "\n[features]\nhooks = true\n"

    for index in range(features_start + 1, next_section):
        if re.match(r"\s*hooks\s*=", lines[index]):
            lines[index] = "hooks = true"
            return "\n".join(lines) + "\n"

    lines.insert(features_start + 1, "hooks = true")
    return "\n".join(lines) + "\n"


def merge_hooks_config(existing: dict[str, Any], new: dict[str, Any], hook_path: str | os.PathLike[str]) -> dict[str, Any]:
    merged = existing.copy() if isinstance(existing, dict) else {}
    merged_hooks = dict(merged.get("hooks") or {})
    marker = str(hook_path)
    for event, entries in new["hooks"].items():
        retained = []
        for entry in merged_hooks.get(event, []):
            commands = [hook.get("command", "") for hook in entry.get("hooks", [])]
            if not any(marker in command or "codex_harness_hook.py" in command for command in commands):
                retained.append(entry)
        retained.extend(entries)
        merged_hooks[event] = retained
    merged["hooks"] = merged_hooks
    return merged


def remove_harness_hooks(existing: dict[str, Any]) -> dict[str, Any]:
    """Remove legacy global Harness4Codex commands while preserving other hooks."""
    cleaned = existing.copy() if isinstance(existing, dict) else {}
    cleaned_hooks: dict[str, Any] = {}
    for event, entries in dict(cleaned.get("hooks") or {}).items():
        retained = []
        for entry in entries:
            commands = [hook.get("command", "") for hook in entry.get("hooks", [])]
            if not any("codex_harness_hook.py" in command for command in commands):
                retained.append(entry)
        cleaned_hooks[event] = retained
    cleaned["hooks"] = cleaned_hooks
    return cleaned


def native_plugin_enabled(config_text: str) -> bool:
    active_harness_section = False
    for raw_line in config_text.splitlines():
        line = raw_line.strip()
        section = re.fullmatch(r"\[plugins\.(.+)\]", line)
        if section:
            plugin_name = section.group(1).strip().strip("\"'")
            active_harness_section = plugin_name.split("@", 1)[0] == "harness4codex"
            continue
        if line.startswith("["):
            active_harness_section = False
            continue
        if active_harness_section and re.fullmatch(r"enabled\s*=\s*true(?:\s*#.*)?", line, re.IGNORECASE):
            return True
    return False


def native_plugin_selector(config_text: str) -> str | None:
    active_plugin: str | None = None
    for raw_line in config_text.splitlines():
        line = raw_line.strip()
        section = re.fullmatch(r"\[plugins\.(.+)\]", line)
        if section:
            candidate = section.group(1).strip().strip("\"'")
            active_plugin = candidate if candidate.split("@", 1)[0] == "harness4codex" else None
            continue
        if line.startswith("["):
            active_plugin = None
            continue
        if active_plugin and re.fullmatch(r"enabled\s*=\s*true(?:\s*#.*)?", line, re.IGNORECASE):
            return active_plugin
    return None


def local_marketplace_source(config_text: str, marketplace: str) -> Path | None:
    active = False
    values: dict[str, str] = {}
    for raw_line in config_text.splitlines():
        line = raw_line.strip()
        section = re.fullmatch(r"\[marketplaces\.(.+)\]", line)
        if section:
            name = section.group(1).strip().strip("\"'")
            active = name == marketplace
            continue
        if line.startswith("["):
            active = False
            continue
        if not active:
            continue
        assignment = re.fullmatch(r"(source_type|source)\s*=\s*(['\"])(.*)\2", line)
        if assignment:
            values[assignment.group(1)] = assignment.group(3)
    if values.get("source_type") != "local" or not values.get("source"):
        return None
    raw_source = values["source"]
    raw_source = raw_source.removeprefix("\\\\?\\")
    return Path(raw_source).expanduser()


def _plugin_manifest(plugin_root: Path) -> dict[str, Any]:
    path = plugin_root / ".codex-plugin" / "plugin.json"
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise RuntimeError(f"invalid Codex plugin manifest: {path}: {exc}") from exc
    if not isinstance(payload, dict) or payload.get("name") != "harness4codex" or not payload.get("version"):
        raise RuntimeError(f"invalid Harness4Codex plugin identity: {path}")
    return payload


def _default_native_runner(command: list[str], codex_home: Path) -> subprocess.CompletedProcess[str]:
    environment = os.environ.copy()
    environment["CODEX_HOME"] = str(codex_home)
    return subprocess.run(
        command,
        capture_output=True,
        text=True,
        check=False,
        env=environment,
    )


def _validate_active_plugin(source: Path, active: Path) -> None:
    source_manifest = _plugin_manifest(source)
    active_manifest = _plugin_manifest(active)
    if active_manifest["version"] != source_manifest["version"]:
        raise RuntimeError(
            f"Codex activated Harness4Codex {active_manifest['version']}; expected {source_manifest['version']}"
        )
    for relative in (Path("hooks/hooks.json"), Path("hooks/codex_harness_hook.py")):
        source_file = source / relative
        active_file = active / relative
        if not active_file.is_file() or active_file.read_bytes() != source_file.read_bytes():
            raise RuntimeError(f"Codex active plugin differs from marketplace source: {relative.as_posix()}")


def _ignore_copy(dir_path: str, names: list[str]) -> set[str]:
    ignored = {
        ".git",
        ".pytest_cache",
        ".pytest_cache_codex",
        ".pytest_tmp_codex",
        ".ruff_cache",
        "__pycache__",
        "graphify-out",
    }
    ignored.update(name for name in names if name.startswith("pytest-cache-files-"))
    ignored.update(name for name in names if name.startswith(".codex_ops_validation"))
    return ignored.intersection(names)


def _atomic_copytree(source: Path, destination: Path, ignore=None) -> None:
    destination.parent.mkdir(parents=True, exist_ok=True)
    token = uuid.uuid4().hex
    staging = destination.parent / f".{destination.name}.staging-{token}"
    backup = destination.parent / f".{destination.name}.backup-{token}"
    shutil.copytree(source, staging, ignore=ignore)
    moved_old = False
    try:
        if destination.exists():
            destination.replace(backup)
            moved_old = True
        staging.replace(destination)
    except Exception:
        if destination.exists() and not moved_old:
            shutil.rmtree(destination, ignore_errors=True)
        if moved_old and backup.exists() and not destination.exists():
            backup.replace(destination)
        raise
    finally:
        if staging.exists():
            shutil.rmtree(staging, ignore_errors=True)
    if backup.exists():
        shutil.rmtree(backup)


def install(
    source: Path,
    codex_home: Path,
    dry_run: bool = False,
    *,
    native_runner: Callable[[list[str], Path], subprocess.CompletedProcess[str]] = _default_native_runner,
) -> dict[str, str]:
    source = source.resolve()
    codex_home = codex_home.expanduser().resolve()
    hooks_config_path = codex_home / "hooks.json"
    config_path = codex_home / "config.toml"
    config_text = config_path.read_text(encoding="utf-8") if config_path.exists() else ""
    selector = native_plugin_selector(config_text)
    hook_mode = "plugin" if selector else "global"
    marketplace_name = selector.split("@", 1)[1] if selector and "@" in selector else ""
    marketplace_root = local_marketplace_source(config_text, marketplace_name) if marketplace_name else None
    plugin_dest = codex_home / "plugins" / "harness4codex"
    if hook_mode == "plugin":
        if marketplace_root is None:
            raise RuntimeError(
                f"Harness4Codex uses native plugin mode, but marketplace {marketplace_name!r} is not local"
            )
        plugin_dest = marketplace_root.resolve() / "plugins" / "harness4codex"
    manifest = _plugin_manifest(source) if hook_mode == "plugin" else None
    version = str(manifest["version"]) if manifest else ""
    active_plugin = (
        codex_home / "plugins" / "cache" / marketplace_name / "harness4codex" / version
        if hook_mode == "plugin"
        else plugin_dest
    )
    skill_dest = codex_home / "skills" / "codex-harness-workflow"
    hook_path = active_plugin / "hooks" / "codex_harness_hook.py"

    result = {
        "source": str(source),
        "codex_home": str(codex_home),
        "plugin": str(plugin_dest),
        "skill": str(skill_dest),
        "hook": str(hook_path),
        "hooks_json": str(hooks_config_path),
        "config_toml": str(config_path),
        "hook_mode": hook_mode,
        "marketplace": marketplace_name,
        "active_plugin": str(active_plugin),
    }

    if dry_run:
        return result

    codex_home.mkdir(parents=True, exist_ok=True)
    _atomic_copytree(source, plugin_dest, ignore=_ignore_copy)

    if hook_mode == "global":
        for skill_source in sorted((source / "skills").iterdir()):
            if skill_source.is_dir() and (skill_source / "SKILL.md").exists():
                _atomic_copytree(skill_source, codex_home / "skills" / skill_source.name)

    existing_hooks: dict[str, Any] = {}
    if hooks_config_path.exists():
        existing_hooks = json.loads(hooks_config_path.read_text(encoding="utf-8"))
    if hook_mode == "plugin":
        command = ["codex", "plugin", "add", selector, "--json"]
        native_result = native_runner(command, codex_home)
        if native_result.returncode != 0:
            detail = native_result.stderr.strip() or native_result.stdout.strip()
            raise RuntimeError(f"Codex native plugin install failed ({native_result.returncode}): {detail}")
        _validate_active_plugin(plugin_dest, active_plugin)
        if hooks_config_path.exists():
            cleaned_hooks = remove_harness_hooks(existing_hooks)
            hooks_config_path.write_text(json.dumps(cleaned_hooks, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    else:
        new_hooks = build_hooks_config(hook_path)
        merged_hooks = merge_hooks_config(existing_hooks, new_hooks, hook_path)
        hooks_config_path.write_text(json.dumps(merged_hooks, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    config_path.write_text(ensure_feature_flag(config_text), encoding="utf-8")

    return result


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Install Harness4Codex into a Codex home directory.")
    parser.add_argument("--source", default=Path(__file__).resolve().parents[1], type=Path)
    parser.add_argument("--codex-home", default=Path.home() / ".codex", type=Path)
    parser.add_argument("--dry-run", action="store_true")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    result = install(args.source, args.codex_home, args.dry_run)
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
