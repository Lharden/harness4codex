from __future__ import annotations

from pathlib import Path
from typing import Any

from .contract import ContractSnapshot

CAPABILITY_EVIDENCE: dict[str, list[str]] = {
    "classification.deterministic-suggestion": [
        "tests/test_sondas_de_producao.py#test_user_prompt_grava_nivel_e_pipeline_do_classificador"
    ],
    "classification.semantic-confirmation": [
        "tests/test_cli.py#test_classification_confirm_updates_transactional_task"
    ],
    "classification.human-override": [
        "tests/test_sondas_de_producao.py#test_classification_confirm_cli_grava_human_override"
    ],
    "state.session-worktree-isolation": ["tests/test_hook.py#test_parallel_sessions_do_not_continue_each_other"],
    "state.transactional-fsm": [
        "tests/test_cli.py#test_task_artifact_evidence_and_completion_commands_drive_fsm",
        "tests/test_hook.py#test_write_after_verification_invalidates_the_gate",
    ],
    "state.ttl-signals": ["tests/test_hook.py#test_session_start_expires_stale_pipeline_before_resuming"],
    "workflow.sdd-v3": ["tests/test_sondas_de_producao.py#test_user_prompt_manda_carregar_workflow_com_fases_sdd"],
    "workflow.human-gates": [
        "tests/test_hook.py#test_stop_escalates_after_two_automatic_continuations_then_allows_human_gate",
        "tests/test_cli.py#test_gate_resolve_approve_releases_escalation_and_resets_continuations",
    ],
    "workflow.adversarial-agents": [
        "tests/test_sondas_de_producao.py#test_user_prompt_manda_carregar_workflow_com_contrato_de_node_result"
    ],
    "workflow.spec-verification": ["tests/test_sondas_de_producao.py#test_task_complete_recusa_sem_verificacao_fresca"],
    "context.graphify": ["tests/test_sondas_de_producao.py#test_graph_cli_grava_artefato_de_contexto"],
    "context.skill-router": [
        "tests/test_sondas_de_producao.py#test_user_prompt_de_docs_injeta_pipeline_de_documentacao"
    ],
    "capability.arsenal": ["tests/test_sondas_de_producao.py#test_arsenal_cli_valida_registro_e_sobreposicao"],
    "memory.wiki-vault": ["tests/test_cli.py#test_memory_compress_and_wiki_cli"],
    "memory.operational-search": [
        "tests/test_hook.py#test_session_history_is_recorded_in_the_shared_memory_store",
        "tests/test_cli.py#test_memory_search_prints_matches",
    ],
    "conversation.branch-keeper": ["tests/test_cli.py#test_branch_cli_offer_approve_open_and_list"],
    "safety.command-policy": ["tests/test_hook.py#test_pre_tool_use_denies_dangerous_git"],
    "integration.harness-lite": [
        "tests/test_harness_lite_adapter.py#test_preview_envelope_matches_harness_lite_task_envelope_v1"
    ],
    "integration.science-harness": [
        "tests/test_science_adapter.py#test_scientific_evidence_prompts_activate_the_read_only_mcp_route"
    ],
    "lifecycle.full-hooks": [
        "tests/test_sondas_de_producao.py#test_hook_por_subprocesso_atende_todo_evento_de_hooks_json"
    ],
    "observability.health-telemetry": ["tests/test_cli.py#test_doctor_json_prints_machine_readiness"],
    "editorial.drop-constrain-retain": [
        "tests/test_sondas_de_producao.py#test_user_prompt_manda_carregar_workflow_com_drop_constrain_retain"
    ],
}


def evidence_is_valid(root: Path, records: list[str]) -> bool:
    """Prova forte: lista nao vazia e cada registro `arquivo#teste` aponta um
    arquivo de verdade que define `def teste(`. Existencia do caminho sozinha
    aceitava lista vazia, diretorio e ancora inexistente."""
    if not records:
        return False
    for record in records:
        path, separator, anchor = record.partition("#")
        if not separator or not anchor:
            return False
        target = root / path
        if not target.is_file():
            return False
        try:
            text = target.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError):
            return False
        if f"def {anchor}(" not in text:
            return False
    return True


def build_capability_report(repository: str | Path | None = None) -> dict[str, Any]:
    root = Path(repository or Path(__file__).resolve().parents[1]).resolve()
    snapshot = ContractSnapshot.load()
    evidence: dict[str, list[str]] = {}
    for capability, records in CAPABILITY_EVIDENCE.items():
        if evidence_is_valid(root, records):
            evidence[capability] = records
    report = snapshot.capability_report(evidence)
    report["snapshot_lock_valid"] = snapshot.verify_lock()
    report["pipeline_fingerprint"] = snapshot.pipeline_fingerprint()
    report["conformant"] = report["snapshot_lock_valid"] and all(
        item["status"] in {"native", "equivalent"} for item in report["capabilities"].values()
    )
    return report
