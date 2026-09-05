from __future__ import annotations

import hashlib
from pathlib import Path

CORE_ENTRIES = (
    ".codex-plugin",
    "harness4codex",
    "hooks",
    "scripts",
    "skills",
    "pyproject.toml",
)
IGNORED_PARTS = {"__pycache__", ".pytest_cache", ".ruff_cache", "graphify-out"}


def plugin_file_manifest(root: str | Path) -> dict[str, str]:
    plugin = Path(root).resolve()
    files: set[Path] = set()
    for entry in CORE_ENTRIES:
        target = plugin / entry
        if target.is_file():
            files.add(target)
        elif target.is_dir():
            files.update(path for path in target.rglob("*") if path.is_file())
    manifest: dict[str, str] = {}
    for path in sorted(files, key=lambda item: item.relative_to(plugin).as_posix()):
        relative = path.relative_to(plugin)
        if any(part in IGNORED_PARTS for part in relative.parts) or path.suffix == ".pyc":
            continue
        manifest[relative.as_posix()] = hashlib.sha256(path.read_bytes()).hexdigest()
    return manifest


def plugin_fingerprint(root: str | Path) -> str:
    digest = hashlib.sha256()
    for relative, content_hash in plugin_file_manifest(root).items():
        digest.update(relative.encode("utf-8"))
        digest.update(b"\0")
        digest.update(content_hash.encode("ascii"))
        digest.update(b"\0")
    return digest.hexdigest()
