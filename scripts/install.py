from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import uuid
from pathlib import Path
from typing import Any

EVENTS = ["SessionStart", "UserPromptSubmit", "PreToolUse", "PermissionRequest", "PostToolUse", "Stop"]


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
            "PreToolUse": [_hook_entry(hook_path, "Harness4Codex guard", "Bash|shell_command|apply_patch")],
            "PermissionRequest": [_hook_entry(hook_path, "Harness4Codex permission", "Bash|shell_command")],
            "PostToolUse": [_hook_entry(hook_path, "Harness4Codex state", "Bash|shell_command|apply_patch")],
            "Stop": [_hook_entry(hook_path, "Harness4Codex verify")],
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


def _ignore_copy(dir_path: str, names: list[str]) -> set[str]:
    ignored = {".git", ".pytest_cache", ".pytest_cache_codex", ".pytest_tmp_codex", "__pycache__"}
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


def install(source: Path, codex_home: Path, dry_run: bool = False) -> dict[str, str]:
    source = source.resolve()
    codex_home = codex_home.expanduser().resolve()
    plugin_dest = codex_home / "plugins" / "harness4codex"
    skill_dest = codex_home / "skills" / "codex-harness-workflow"
    hook_path = plugin_dest / "hooks" / "codex_harness_hook.py"
    hooks_config_path = codex_home / "hooks.json"
    config_path = codex_home / "config.toml"

    result = {
        "source": str(source),
        "codex_home": str(codex_home),
        "plugin": str(plugin_dest),
        "skill": str(skill_dest),
        "hook": str(hook_path),
        "hooks_json": str(hooks_config_path),
        "config_toml": str(config_path),
    }

    if dry_run:
        return result

    codex_home.mkdir(parents=True, exist_ok=True)
    _atomic_copytree(source, plugin_dest, ignore=_ignore_copy)

    _atomic_copytree(source / "skills" / "codex-harness-workflow", skill_dest)

    new_hooks = build_hooks_config(hook_path)
    existing_hooks: dict[str, Any] = {}
    if hooks_config_path.exists():
        existing_hooks = json.loads(hooks_config_path.read_text(encoding="utf-8"))
    merged_hooks = merge_hooks_config(existing_hooks, new_hooks, hook_path)
    hooks_config_path.write_text(json.dumps(merged_hooks, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    config_text = config_path.read_text(encoding="utf-8") if config_path.exists() else ""
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
