from __future__ import annotations

import hashlib
import json
from pathlib import Path
import subprocess
from typing import Any


IGNORED_PARTS = {".git", "graphify-out", ".venv", "venv", "node_modules", "__pycache__"}


def collect_graph_context(
    repository: str | Path,
    *,
    task_id: str,
    scope_id: str,
    query: str,
    query_result: dict[str, Any] | None = None,
    graphify_version: str | None = None,
) -> dict[str, Any]:
    root = Path(repository).resolve()
    graph = root / "graphify-out" / "graph.json"
    exceptions: list[dict[str, str]] = []
    freshness = "unavailable"
    graph_hash = None
    if graph.exists():
        graph_hash = _sha256(graph)
        latest_source = _latest_source_mtime(root)
        freshness = "fresh" if graph.stat().st_mtime >= latest_source else "stale"
        if freshness == "stale":
            exceptions.append(
                {"code": "GRAPH_STALE", "message": "graph.json predates repository source files"}
            )
    else:
        exceptions.append({"code": "GRAPH_MISSING", "message": "graphify-out/graph.json is absent"})

    result = query_result or {}
    query_record = {
        "mode": "query",
        "text_hash": hashlib.sha256(query.encode("utf-8")).hexdigest(),
        "returned_nodes": list(result.get("nodes") or []),
        "returned_communities": list(result.get("communities") or []),
        "candidate_files": list(result.get("files") or []),
        "duration_ms": int(result.get("duration_ms") or 0),
    }
    return {
        "schema_version": 1,
        "task_id": task_id,
        "scope_id": scope_id,
        "repository_head": _git_head(root),
        "graph_head": _graph_head(root),
        "graphify_version": graphify_version,
        "manifest_hash": graph_hash,
        "freshness": freshness,
        "queries": [query_record],
        "exceptions": exceptions,
    }


def write_graph_context(path: str | Path, artifact: dict[str, Any]) -> Path:
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(artifact, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return target


def _latest_source_mtime(root: Path) -> float:
    latest = 0.0
    for path in root.rglob("*"):
        if not path.is_file() or any(part in IGNORED_PARTS for part in path.relative_to(root).parts):
            continue
        try:
            latest = max(latest, path.stat().st_mtime)
        except OSError:
            continue
    return latest


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _git_head(root: Path) -> str | None:
    try:
        result = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            cwd=root,
            capture_output=True,
            check=False,
            text=True,
            timeout=3,
        )
    except (OSError, subprocess.TimeoutExpired):
        return None
    return result.stdout.strip() if result.returncode == 0 else None


def _graph_head(root: Path) -> str | None:
    manifest = root / "graphify-out" / "manifest.json"
    if not manifest.exists():
        return None
    try:
        payload = json.loads(manifest.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    for key in ("repository_head", "git_head", "head"):
        if payload.get(key):
            return str(payload[key])
    return None
