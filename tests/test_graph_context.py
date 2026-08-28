import json
import os
from pathlib import Path

from harness4codex.graph_context import collect_graph_context


def test_graph_context_records_hash_head_query_and_freshness(tmp_path: Path):
    (tmp_path / "src.py").write_text("VALUE = 1\n", encoding="utf-8")
    graph_dir = tmp_path / "graphify-out"
    graph_dir.mkdir()
    graph = graph_dir / "graph.json"
    graph.write_text(json.dumps({"nodes": [{"id": "src.VALUE"}]}), encoding="utf-8")
    os.utime(graph, (graph.stat().st_atime + 10, graph.stat().st_mtime + 10))

    artifact = collect_graph_context(
        tmp_path,
        task_id="t-1",
        scope_id="scope",
        query="where is VALUE used?",
        query_result={"nodes": ["src.VALUE"], "communities": ["src"], "files": ["src.py"]},
    )

    assert artifact["schema_version"] == 1
    assert artifact["freshness"] == "fresh"
    assert artifact["manifest_hash"]
    assert artifact["queries"][0]["text_hash"]
    assert artifact["queries"][0]["candidate_files"] == ["src.py"]


def test_missing_and_stale_graph_degrade_explicitly(tmp_path: Path):
    missing = collect_graph_context(tmp_path, task_id="t", scope_id="s", query="q")
    assert missing["freshness"] == "unavailable"
    assert missing["exceptions"][0]["code"] == "GRAPH_MISSING"

    graph_dir = tmp_path / "graphify-out"
    graph_dir.mkdir()
    graph = graph_dir / "graph.json"
    graph.write_text("{}", encoding="utf-8")
    source = tmp_path / "new.py"
    source.write_text("pass\n", encoding="utf-8")
    os.utime(source, (graph.stat().st_atime + 20, graph.stat().st_mtime + 20))

    stale = collect_graph_context(tmp_path, task_id="t", scope_id="s", query="q")
    assert stale["freshness"] == "stale"
    assert stale["exceptions"][0]["code"] == "GRAPH_STALE"
