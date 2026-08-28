from __future__ import annotations

from pathlib import Path
from typing import Any

from .contract import ContractSnapshot


CAPABILITY_EVIDENCE: dict[str, list[str]] = {
    "classification.deterministic-suggestion": ["harness4codex/classifier.py#classify_prompt", "tests/test_classifier.py"],
    "classification.semantic-confirmation": ["harness4codex/state_db.py#confirm_classification", "tests/test_transactional_state.py"],
    "classification.human-override": ["harness4codex/cli.py#_cmd_classification_confirm", "tests/test_cli.py"],
    "state.session-worktree-isolation": ["harness4codex/state.py#store_for_payload", "tests/test_state.py"],
    "state.transactional-fsm": ["harness4codex/state_db.py#HarnessDatabase", "tests/test_transactional_state.py"],
    "state.ttl-signals": ["harness4codex/state_db.py#expire_stale_task", "tests/test_transactional_state.py"],
    "workflow.sdd-v3": ["skills/codex-harness-workflow/SKILL.md", "tests/test_packaging.py"],
    "workflow.human-gates": ["harness4codex/state_db.py#open_gate", "tests/test_transactional_state.py"],
    "workflow.adversarial-agents": ["harness4codex/agent_workflows.py#WorkflowCensus", "skills/grill-me/SKILL.md"],
    "workflow.spec-verification": ["skills/verify-against-spec/SKILL.md", "skills/verify-against-spec/templates/verification-template.md"],
    "context.graphify": ["harness4codex/graph_context.py#collect_graph_context", "tests/test_graph_context.py"],
    "context.skill-router": ["harness4codex/classifier.py", "skills/codex-harness-workflow/SKILL.md"],
    "capability.arsenal": ["harness4codex/arsenal.py#ArsenalRegistry", "tests/test_arsenal.py"],
    "memory.wiki-vault": ["harness4codex/wiki.py#WikiIndex", "skills/wiki-query/SKILL.md"],
    "memory.operational-search": ["harness4codex/memory.py#HarnessMemoryStore", "tests/test_memory.py"],
    "conversation.branch-keeper": ["harness4codex/branches.py#BranchKeeper", "tests/test_branches.py"],
    "safety.command-policy": ["harness4codex/command_policy.py#evaluate_command", "tests/test_command_policy.py"],
    "integration.harness-lite": ["harness4codex/harness_lite_adapter.py", "tests/test_harness_lite_adapter.py"],
    "integration.science-harness": ["harness4codex/science_adapter.py", "tests/test_science_adapter.py"],
    "lifecycle.full-hooks": ["hooks/hooks.json", "tests/test_packaging.py"],
    "observability.health-telemetry": ["harness4codex/diagnostics.py#run_doctor", "tests/test_diagnostics.py"],
    "editorial.drop-constrain-retain": ["skills/codex-harness-workflow/SKILL.md", "tests/test_packaging.py"],
}


def build_capability_report(repository: str | Path | None = None) -> dict[str, Any]:
    root = Path(repository or Path(__file__).resolve().parents[1]).resolve()
    snapshot = ContractSnapshot.load()
    evidence: dict[str, list[str]] = {}
    for capability, records in CAPABILITY_EVIDENCE.items():
        if all((root / record.split("#", 1)[0]).exists() for record in records):
            evidence[capability] = records
    report = snapshot.capability_report(evidence)
    report["snapshot_lock_valid"] = snapshot.verify_lock()
    report["pipeline_fingerprint"] = snapshot.pipeline_fingerprint()
    report["conformant"] = report["snapshot_lock_valid"] and all(
        item["status"] in {"native", "equivalent"} for item in report["capabilities"].values()
    )
    return report
