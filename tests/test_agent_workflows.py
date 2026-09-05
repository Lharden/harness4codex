import pytest

from harness4codex.agent_workflows import (
    NodeResult,
    WorkflowCensus,
    WorkflowContractError,
)


def test_node_census_reconciles_only_complete_unique_results():
    census = WorkflowCensus(
        workflow_id="wf-1",
        nodes={
            "security": {"role": "security", "dependencies": []},
            "failure": {"role": "failure", "dependencies": []},
        },
    )
    census.accept(
        NodeResult(
            node_id="security",
            status="complete",
            summary="one finding",
            artifacts=["review/security.md"],
            evidence=[{"path": "src/api.py", "line": 12}],
            risks=[],
            questions=[],
        )
    )

    report = census.reconcile()

    assert report["complete"] is False
    assert report["missing"] == ["failure"]


def test_node_result_contract_rejects_unknown_duplicate_and_unsupported_status():
    census = WorkflowCensus(workflow_id="wf-1", nodes={"a": {"role": "reviewer"}})
    result = NodeResult("a", "complete", "ok", [], [], [], [])
    census.accept(result)
    with pytest.raises(WorkflowContractError, match="duplicate"):
        census.accept(result)
    with pytest.raises(WorkflowContractError, match="unknown"):
        WorkflowCensus("wf-2", {"a": {}}).accept(NodeResult("b", "complete", "", [], [], [], []))
    with pytest.raises(WorkflowContractError, match="status"):
        NodeResult("a", "maybe", "", [], [], [], []).validate()


def test_census_requires_satisfied_dependencies_for_completion():
    census = WorkflowCensus(
        "wf",
        {
            "producer": {"role": "producer", "dependencies": []},
            "review": {"role": "reviewer", "dependencies": ["producer"]},
        },
    )
    with pytest.raises(WorkflowContractError, match="dependency"):
        census.accept(NodeResult("review", "complete", "", [], [], [], []))
