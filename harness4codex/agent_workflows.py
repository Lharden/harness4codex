from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any


class WorkflowContractError(ValueError):
    pass


@dataclass(frozen=True)
class NodeResult:
    node_id: str
    status: str
    summary: str
    artifacts: list[str]
    evidence: list[dict[str, Any]]
    risks: list[str]
    questions: list[str]

    def validate(self) -> None:
        if self.status not in {"complete", "partial", "blocked", "failed"}:
            raise WorkflowContractError(f"unsupported node status: {self.status}")
        if not self.node_id.strip():
            raise WorkflowContractError("node_id is required")
        if self.status == "complete" and self.questions:
            raise WorkflowContractError("complete node cannot have unresolved questions")

    def to_dict(self) -> dict[str, Any]:
        self.validate()
        return asdict(self)


class WorkflowCensus:
    def __init__(self, workflow_id: str, nodes: dict[str, dict[str, Any]]):
        if not workflow_id or not nodes:
            raise WorkflowContractError("workflow id and node census are required")
        self.workflow_id = workflow_id
        self.nodes = nodes
        self.results: dict[str, NodeResult] = {}
        unknown_dependencies = {
            dependency
            for node in nodes.values()
            for dependency in node.get("dependencies", [])
            if dependency not in nodes
        }
        if unknown_dependencies:
            raise WorkflowContractError(f"unknown dependencies: {sorted(unknown_dependencies)}")

    def accept(self, result: NodeResult) -> None:
        result.validate()
        if result.node_id not in self.nodes:
            raise WorkflowContractError(f"unknown node: {result.node_id}")
        if result.node_id in self.results:
            raise WorkflowContractError(f"duplicate node result: {result.node_id}")
        dependencies = self.nodes[result.node_id].get("dependencies", [])
        missing = [node_id for node_id in dependencies if self.results.get(node_id) is None]
        if missing:
            raise WorkflowContractError(f"node dependency not satisfied: {missing}")
        self.results[result.node_id] = result

    def reconcile(self) -> dict[str, Any]:
        missing = sorted(set(self.nodes) - set(self.results))
        failed = sorted(node_id for node_id, result in self.results.items() if result.status != "complete")
        return {
            "workflow_id": self.workflow_id,
            "expected": sorted(self.nodes),
            "received": sorted(self.results),
            "missing": missing,
            "failed": failed,
            "complete": not missing and not failed,
            "results": {node_id: result.to_dict() for node_id, result in self.results.items()},
        }
