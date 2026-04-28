from pathlib import Path

from harness4codex.workflow import find_workflow, load_workflow


def test_find_workflow_walks_up_from_child_directory(tmp_path):
    root = tmp_path / "repo"
    child = root / "src" / "pkg"
    child.mkdir(parents=True)
    workflow = root / "WORKFLOW.md"
    workflow.write_text("# Workflow\nShip carefully.\n", encoding="utf-8")

    assert find_workflow(child) == workflow


def test_load_workflow_parses_frontmatter_defaults_and_body(tmp_path):
    workflow = tmp_path / "WORKFLOW.md"
    workflow.write_text(
        "---\n"
        "project: Demo\n"
        "verification:\n"
        "  commands:\n"
        "    - python -m pytest\n"
        "orchestration:\n"
        "  active_states:\n"
        "    - Ready\n"
        "    - In Progress\n"
        "  max_turns: 7\n"
        "---\n"
        "# Demo Workflow\n"
        "Use small reviewed changes.\n",
        encoding="utf-8",
    )

    definition = load_workflow(tmp_path)

    assert definition is not None
    assert definition.config["project"] == "Demo"
    assert definition.verification_commands == ["python -m pytest"]
    assert definition.active_states == ["Ready", "In Progress"]
    assert definition.max_turns == 7
    assert definition.prompt_template.startswith("# Demo Workflow")


def test_render_for_prompt_is_compact_and_actionable(tmp_path):
    (tmp_path / "WORKFLOW.md").write_text(
        "---\nverification:\n  commands:\n    - pytest -q\nhandoff_state: Human Review\n---\n"
        "# Workflow\nAttach proof before review.\n",
        encoding="utf-8",
    )

    rendered = load_workflow(tmp_path).render_for_prompt(max_body_chars=80)

    assert "Repo WORKFLOW.md" in rendered
    assert "pytest -q" in rendered
    assert "Human Review" in rendered
    assert "Attach proof before review" in rendered


def test_missing_workflow_returns_none(tmp_path):
    isolated_repo = tmp_path / "isolated"
    isolated_repo.mkdir()
    (isolated_repo / ".git").mkdir()

    assert find_workflow(isolated_repo) is None
    assert load_workflow(isolated_repo) is None
