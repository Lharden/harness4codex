from pathlib import Path

import pytest

from harness4codex.memory_compression import CompressionError, compress_memory_file


def test_compression_is_reversible_and_idempotent(tmp_path: Path):
    path = tmp_path / "recent.md"
    path.write_text("# Today\n\nBasically, I think this is actually ready.\n`git status`\n", encoding="utf-8")

    first = compress_memory_file(path)
    second = compress_memory_file(path)

    assert first["saved_chars"] > 0
    assert path.with_name("recent.original.md").exists()
    assert second["saved_chars"] == 0
    assert "`git status`" in path.read_text(encoding="utf-8")


@pytest.mark.parametrize("name", ["AGENTS.md", "MEMORY.md", "core-memories.md"])
def test_protected_memory_names_are_rejected(tmp_path: Path, name: str):
    path = tmp_path / name
    path.write_text("notes", encoding="utf-8")
    with pytest.raises(CompressionError, match="protected"):
        compress_memory_file(path)


def test_spec_markers_are_rejected_even_in_secondary_file(tmp_path: Path):
    path = tmp_path / "recent.md"
    path.write_text("REQ-001: Given x When y Then z", encoding="utf-8")
    with pytest.raises(CompressionError, match="specification"):
        compress_memory_file(path)
