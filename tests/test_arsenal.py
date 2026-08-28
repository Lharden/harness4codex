from pathlib import Path

import pytest

from harness4codex.arsenal import ArsenalError, ArsenalRegistry


def test_arsenal_validates_vocab_overlap_and_budget(tmp_path: Path):
    registry = ArsenalRegistry(tmp_path / "arsenal.json", budget=2)
    registry.define_capabilities(["knowledge-graph", "semantic-search", "sdd"])
    registry.add_tool("graphify", ["knowledge-graph", "semantic-search"], status="adopted")

    assert registry.overlap(["semantic-search"]) == ["graphify"]
    assert registry.budget_report() == {"budget": 2, "used": 1, "available": 1, "fits": True}

    with pytest.raises(ArsenalError, match="vocabulary"):
        registry.add_tool("unknown", ["imaginary-capability"], status="trial")


def test_absorbed_capability_requires_existing_destination(tmp_path: Path):
    registry = ArsenalRegistry(tmp_path / "arsenal.json")
    registry.define_capabilities(["sdd"])
    with pytest.raises(ArsenalError, match="destination"):
        registry.add_tool("source", ["sdd"], status="absorbed", absorbed_into=tmp_path / "missing.py")

    target = tmp_path / "workflow.py"
    target.write_text("# implementation\n", encoding="utf-8")
    registry.add_tool("source", ["sdd"], status="absorbed", absorbed_into=target)

    assert registry.check()["ok"] is True
