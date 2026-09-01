from __future__ import annotations

from pathlib import Path
from typing import Any

from .contract import ContractSnapshot

CAPABILITY_EVIDENCE: dict[str, list[str]] = {
    "classification.deterministic-suggestion": ["tests/test_classifier.py#test_bug_promotes_debugging_and_tdd"],
    "classification.semantic-confirmation": ["tests/test_transactional_state.py#test_semantic_confirmation_records_provenance_and_replaces_pipeline"],
    "classification.human-override": ["tests/test_cli.py#test_classification_confirm_updates_transactional_task"],
    "state.session-worktree-isolation": ["tests/test_state.py#test_store_for_payload_scopes_by_session_and_cwd"],
    "state.transactional-fsm": ["tests/test_transactional_state.py#test_fresh_test_evidence_allows_completion_and_file_change_invalidates_it"],
    "state.ttl-signals": ["tests/test_transactional_state.py#test_stale_task_ttl_abandons_pipeline_and_releases_scope"],
    "workflow.sdd-v3": ["tests/test_packaging.py#test_codex_native_sdd_skill_surface_is_packaged"],
    "workflow.human-gates": ["tests/test_transactional_state.py#test_human_gate_sets_awaiting_gate_and_resolution_advances"],
    "workflow.adversarial-agents": ["tests/test_agent_workflows.py#test_node_census_reconciles_only_complete_unique_results"],
    "workflow.spec-verification": ["tests/test_packaging.py#test_sdd_templates_are_packaged"],
    "context.graphify": ["tests/test_graph_context.py#test_graph_context_records_hash_head_query_and_freshness"],
    "context.skill-router": ["tests/test_classifier.py#test_openai_docs_prompt_uses_the_installed_openai_docs_skill"],
    "capability.arsenal": ["tests/test_arsenal.py#test_arsenal_validates_vocab_overlap_and_budget"],
    "memory.wiki-vault": ["tests/test_wiki.py#test_wiki_index_returns_cited_sections_and_confidence"],
    "memory.operational-search": ["tests/test_memory.py#test_memory_records_and_searches_history"],
    "conversation.branch-keeper": ["tests/test_branches.py#test_each_branch_approval_resolves_only_its_own_gate"],
    "safety.command-policy": ["tests/test_command_policy.py#test_destructive_command_in_chain_is_denied"],
    "integration.harness-lite": ["tests/test_harness_lite_adapter.py#test_preview_envelope_matches_harness_lite_task_envelope_v1"],
    "integration.science-harness": ["tests/test_science_adapter.py#test_scientific_evidence_prompts_activate_the_read_only_mcp_route"],
    "lifecycle.full-hooks": ["tests/test_packaging.py#test_plugin_registers_full_codex_lifecycle"],
    "observability.health-telemetry": ["tests/test_diagnostics.py#test_doctor_fails_when_active_plugin_is_older_than_marketplace_source"],
    "editorial.drop-constrain-retain": ["tests/test_packaging.py#test_workflow_skill_drives_the_transactional_contract"],
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
