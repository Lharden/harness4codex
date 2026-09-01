# Graph Report - operational-equipotence  (2026-09-01)

## Corpus Check
- 91 files · ~33,720 words
- Verdict: corpus is large enough that graph structure adds value.

## Summary
- 1090 nodes · 2055 edges · 85 communities (65 shown, 20 thin omitted)
- Extraction: 97% EXTRACTED · 3% INFERRED · 0% AMBIGUOUS · INFERRED: 61 edges (avg confidence: 0.61)
- Token cost: 0 input · 0 output

## Graph Freshness
- Built from commit: `42142e3c`
- Run `git rev-parse HEAD` and compare to check if the graph is stale.
- Run `graphify update .` after code changes (no API cost).

## Community Hubs (Navigation)
- hook.py
- cli.py
- HarnessStateStore
- HarnessMemoryStore
- load_workflow
- install
- test_orchestration.py
- classify_prompt
- run_doctor
- PLANO_AUTOREFORMA_HARNESS4CODEX.md
- 10. Fase 5 — Graphify como fase nativa
- inspect_command
- 14. Fase 9 — Orquestração real
- Harness4Codex
- 13. Fase 8 — Shell AST e policy engine
- 15. Fase 10 — Testes avançados
- 18. Fase 13 — Canário e rollout
- 19. Protocolo de comparação com Harness4Claude
- Symphony Memory Workflow Implementation Plan
- Symphony Memory Workflow Design
- science_context
- 11. Fase 6 — Índice gráfico e recuperação
- 12. Fase 7 — Evidência forte e Stop gate
- 8. Fase 3 — Máquina de pipeline formal
- 9. Fase 4 — Confirmação semântica estruturada
- Codex App Multitask State Implementation Plan
- 7. Fase 2 — Endurecimento do state store
- Codex Harness Workflow
- Harness4Codex implementation plan
- 5. Fase 0 — Linha de base e harness de teste do harness
- 6. Fase 1 — Observabilidade estruturada
- 16. Fase 11 — Process mining e melhoria orientada por dados
- 2. Princípio de otimização
- 3. Regras de execução
- 17. Fase 12 — Otimização de hot paths
- harness4codex/__init__.py
- scripts/__init__.py
- install.sh script
- WORKFLOW.md
- harness4codex
- install.ps1
- 4. Artefatos obrigatórios antes da reforma
- 11. Fase 6 — Índice gráfico e recuperação
- 12. Fase 7 — Evidência forte e Stop gate
- 8. Fase 3 — Máquina de pipeline formal
- 9. Fase 4 — Confirmação semântica estruturada
- required
- type
- Verification Report — {Feature}
- Codex App Multitask State Implementation Plan
- 7. Fase 2 — Endurecimento do state store
- Harness4Codex implementation plan
- 5. Fase 0 — Linha de base e harness de teste do harness
- 6. Fase 1 — Observabilidade estruturada
- classification.schema.json
- risk_flags
- enum
- enum
- task-state.schema.json
- enum
- 16. Fase 11 — Process mining e melhoria orientada por dados
- 2. Princípio de otimização
- 4. Artefatos obrigatórios antes da reforma
- scripts/__init__.py
- install.sh
- Harness4Codex Workflow
- assimilar/SKILL.md
- branch-out/SKILL.md
- compress-memory/SKILL.md
- design-doc/SKILL.md
- discuss/SKILL.md
- graph-context/SKILL.md
- grill-me/SKILL.md
- security-scan-python/SKILL.md
- validate-plan/SKILL.md
- verify-against-spec/SKILL.md
- wiki-query/SKILL.md
- write-spec-light/SKILL.md
- write-spec/SKILL.md
- Any
- Path
- __main__.py
- Path

## God Nodes (most connected - your core abstractions)
1. `HarnessDatabase` - 81 edges
2. `HarnessStateStore` - 65 edges
3. `handle_payload()` - 38 edges
4. `StateTransitionError` - 30 edges
5. `_build_parser()` - 29 edges
6. `HarnessMemoryStore` - 28 edges
7. `ContractSnapshot` - 24 edges
8. `run_doctor()` - 21 edges
9. `Classification` - 19 edges
10. `install()` - 19 edges

## Surprising Connections (you probably didn't know these)
- `test_census_requires_satisfied_dependencies_for_completion()` --indirect_call--> `WorkflowContractError`  [INFERRED]
  tests/test_agent_workflows.py → harness4codex/agent_workflows.py
- `test_node_result_contract_rejects_unknown_duplicate_and_unsupported_status()` --indirect_call--> `WorkflowContractError`  [INFERRED]
  tests/test_agent_workflows.py → harness4codex/agent_workflows.py
- `test_absorbed_capability_requires_existing_destination()` --indirect_call--> `ArsenalError`  [INFERRED]
  tests/test_arsenal.py → harness4codex/arsenal.py
- `test_arsenal_validates_vocab_overlap_and_budget()` --indirect_call--> `ArsenalError`  [INFERRED]
  tests/test_arsenal.py → harness4codex/arsenal.py
- `test_branch_limits_and_topic_deduplication()` --indirect_call--> `BranchPolicyError`  [INFERRED]
  tests/test_branches.py → harness4codex/branches.py

## Import Cycles
- None detected.

## Communities (85 total, 20 thin omitted)

### Community 0 - "hook.py"
Cohesion: 0.07
Nodes (72): _normalize(), science_context(), wants_science_evidence(), test_ordinary_bugfix_does_not_activate_science_route(), test_scientific_evidence_prompts_activate_the_read_only_mcp_route(), _append_lite_preview(), _append_science_context(), _append_workflow_context() (+64 more)

### Community 1 - "cli.py"
Cohesion: 0.12
Nodes (24): build_task_envelope(), _canonical(), _digest(), evidence_bundle_is_acceptable(), execution_is_enabled(), HarnessLiteClient, lite_route_for(), LiteCallResult (+16 more)

### Community 2 - "HarnessStateStore"
Cohesion: 0.08
Nodes (41): Classification, run(), default_harness_home(), default_state(), HarnessStateError, HarnessStateStore, list_session_states(), Path (+33 more)

### Community 3 - "HarnessMemoryStore"
Cohesion: 0.16
Nodes (13): ConsolidationReport, HarnessMemoryStore, MemoryConsolidator, Any, Connection, Path, test_consolidator_creates_auditable_proposals_without_editing_files(), test_consolidator_reads_session_event_logs() (+5 more)

### Community 4 - "load_workflow"
Cohesion: 0.08
Nodes (41): BranchKeeper, BranchPolicyError, _jaccard(), _normalize(), Any, Path, ValueError, _slug() (+33 more)

### Community 5 - "install"
Cohesion: 0.14
Nodes (32): CompletedProcess, _atomic_copytree(), build_hooks_config(), _default_native_runner(), ensure_feature_flag(), _hook_entry(), _ignore_copy(), install() (+24 more)

### Community 6 - "test_orchestration.py"
Cohesion: 0.06
Nodes (45): additionalProperties, type, type, type, type, $id, null, phase (+37 more)

### Community 7 - "classify_prompt"
Cohesion: 0.10
Nodes (25): classify_prompt(), _matches(), _normalize(), build_capability_report(), Any, Path, ContractSnapshot, ContractSnapshotError (+17 more)

### Community 8 - "run_doctor"
Cohesion: 0.06
Nodes (40): additionalProperties, type, type, type, type, $id, null, status (+32 more)

### Community 9 - "PLANO_AUTOREFORMA_HARNESS4CODEX.md"
Cohesion: 0.06
Nodes (36): additionalProperties, items, type, items, type, items, type, items (+28 more)

### Community 10 - "10. Fase 5 — Graphify como fase nativa"
Cohesion: 0.04
Nodes (44): minLength, type, additionalProperties, additionalProperties, properties, required, type, additionalProperties (+36 more)

### Community 11 - "inspect_command"
Cohesion: 0.09
Nodes (53): ArgumentParser, git_base_revision(), _branch_keeper(), _build_parser(), _cmd_arsenal_check(), _cmd_arsenal_overlap(), _cmd_artifact_record(), _cmd_branch_approve() (+45 more)

### Community 12 - "14. Fase 9 — Orquestração real"
Cohesion: 0.18
Nodes (19): test_blocks_clean_force(), test_blocks_force_push(), test_blocks_reset_hard(), test_normal_push_warns_without_blocking(), test_safe_command_allowed(), CommandInvocation, evaluate_command(), _evaluate_invocation() (+11 more)

### Community 13 - "Harness4Codex"
Cohesion: 0.22
Nodes (8): CLI, Codex App Multitask Safety, Harness4Codex, Install, Notes, Validate, What it adds, Workflow Policy

### Community 14 - "13. Fase 8 — Shell AST e policy engine"
Cohesion: 0.25
Nodes (8): ArsenalError, ArsenalRegistry, Any, Path, ValueError, Path, test_absorbed_capability_requires_existing_destination(), test_arsenal_validates_vocab_overlap_and_budget()

### Community 15 - "15. Fase 10 — Testes avançados"
Cohesion: 0.21
Nodes (11): test_policy_allows_issue_when_blockers_terminal(), test_policy_blocks_issue_with_active_blocker(), test_retry_backoff_is_exponential_and_capped(), test_workspace_manager_creates_deterministic_issue_workspace(), test_workspace_manager_sanitizes_identifier(), Issue, OrchestrationPolicy, Path (+3 more)

### Community 16 - "18. Fase 13 — Canário e rollout"
Cohesion: 0.32
Nodes (8): NodeResult, Any, ValueError, WorkflowCensus, WorkflowContractError, test_census_requires_satisfied_dependencies_for_completion(), test_node_census_reconciles_only_complete_unique_results(), test_node_result_contract_rejects_unknown_duplicate_and_unsupported_status()

### Community 17 - "19. Protocolo de comparação com Harness4Claude"
Cohesion: 0.16
Nodes (16): find_workflow(), _indent_of(), load_workflow(), _parse_block(), _parse_limited_yaml(), _parse_scalar(), Any, Path (+8 more)

### Community 18 - "Symphony Memory Workflow Implementation Plan"
Cohesion: 0.14
Nodes (13): 0. Mandato, 17. Fase 12 — Otimização de hot paths, 1. Capacidades atuais que devem ser preservadas, 20. Critérios finais de aceitação, 21. Relatório final obrigatório, 22. Ordem resumida, 4.1 Inventário, 4.2 Baseline (+5 more)

### Community 19 - "Symphony Memory Workflow Design"
Cohesion: 0.18
Nodes (11): type, minimum, type, properties, kind, owner_epoch, scope_id, status (+3 more)

### Community 20 - "science_context"
Cohesion: 0.17
Nodes (12): type, maximum, minimum, type, type, null, string, agreed (+4 more)

### Community 21 - "11. Fase 6 — Índice gráfico e recuperação"
Cohesion: 0.24
Nodes (18): _active_plugin(), DiagnosticCheck, DoctorReport, _load_config(), _marketplace_plugin(), Path, _read_plugin_manifest(), _registered_hooks() (+10 more)

### Community 22 - "12. Fase 7 — Evidência forte e Stop gate"
Cohesion: 0.18
Nodes (11): minLength, type, properties, kind, pipeline_id, suggested, task_id, minLength (+3 more)

### Community 23 - "8. Fase 3 — Máquina de pipeline formal"
Cohesion: 0.20
Nodes (10): 10. Fase 5 — Graphify como fase nativa, Artefato, Atualização, Gate, Métricas, Novo step, Objetivo, Política por classe (+2 more)

### Community 24 - "9. Fase 4 — Confirmação semântica estruturada"
Cohesion: 0.20
Nodes (10): items, type, items, type, type, items, type, artifacts (+2 more)

### Community 25 - "Codex App Multitask State Implementation Plan"
Cohesion: 0.22
Nodes (9): 14. Fase 9 — Orquestração real, Advisory, Controlled, Etapas, Gate, Invariantes, Objetivo, Observe (+1 more)

### Community 26 - "7. Fase 2 — Endurecimento do state store"
Cohesion: 0.22
Nodes (9): kind, phase, scope_id, status, task_id, tier, required, pipeline (+1 more)

### Community 27 - "Codex Harness Workflow"
Cohesion: 0.22
Nodes (8): Canonical execution, Delegated work, Editorial control, Evidence and completion, Harness4Codex Workflow, Human gates, Start or resume, Stop and recovery

### Community 29 - "Harness4Codex implementation plan"
Cohesion: 0.22
Nodes (8): Assumptions, Boundaries and data, Clarifications, Failure behavior, {Feature} — Specification, Objective and success, P1 User Story — {title}, P2/P3 Stories

### Community 30 - "5. Fase 0 — Linha de base e harness de teste do harness"
Cohesion: 0.25
Nodes (8): 13. Fase 8 — Shell AST e policy engine, Decisões, Gate, Limites de `WORKFLOW.md`, Objetivo, OPA/Rego, Parser, Policy input

### Community 31 - "6. Fase 1 — Observabilidade estruturada"
Cohesion: 0.25
Nodes (8): 15. Fase 10 — Testes avançados, Classificador, Concurrency, Memória, Metamorphic, Mutation testing, Property-based, Workflow

### Community 32 - "16. Fase 11 — Process mining e melhoria orientada por dados"
Cohesion: 0.25
Nodes (8): 18. Fase 13 — Canário e rollout, C0, C1, C2/C3, CR/DOCS, Fixtures, Rollback, Shadow

### Community 33 - "2. Princípio de otimização"
Cohesion: 0.25
Nodes (8): 19. Protocolo de comparação com Harness4Claude, Corpus, Hard constraints, Performance, Qualidade, Restrições, Resultado, Transferência

### Community 34 - "3. Regras de execução"
Cohesion: 0.25
Nodes (8): enum, architecture, bug, docs, feature, question, refactor, review

### Community 35 - "17. Fase 12 — Otimização de hot paths"
Cohesion: 0.25
Nodes (8): suggested, enum, abandoned, active, awaiting_gate, done, rolled_back, verified

### Community 37 - "scripts/__init__.py"
Cohesion: 0.25
Nodes (7): Branch Seed — {name}, First action, Minimum context, Origin, Report back, The branch, Why it branched

### Community 38 - "install.sh script"
Cohesion: 0.25
Nodes (7): Architecture and components, Data and contracts, Failure, migration and rollback, {Feature} — Design, Risks and decisions, Test strategy and observability, Traceability

### Community 39 - "WORKFLOW.md"
Cohesion: 0.25
Nodes (7): Assumptions, Clarifications, {Feature} — Spec Light, Objective, Requirements, Scope, Success

### Community 41 - "install.ps1"
Cohesion: 0.29
Nodes (6): Symphony Memory Workflow Implementation Plan, Task 1: Workflow Loader, Task 2: SQLite Memory And Consolidation, Task 3: CLI Status Surface, Task 4: Orchestration Primitives, Task 5: Install, Verify, Commit, Push

### Community 42 - "4. Artefatos obrigatórios antes da reforma"
Cohesion: 0.29
Nodes (6): Architecture, Context, Goals, Non-Goals, Safety, Symphony Memory Workflow Design

### Community 43 - "11. Fase 6 — Índice gráfico e recuperação"
Cohesion: 0.29
Nodes (7): 11. Fase 6 — Índice gráfico e recuperação, Depois: ranking local, Gate, Graph sidecar, GraphBLAS, HNSW, Primeiro: FTS5

### Community 44 - "12. Fase 7 — Evidência forte e Stop gate"
Cohesion: 0.29
Nodes (7): 12. Fase 7 — Evidência forte e Stop gate, Evidência mínima, Gate, Objetivo, Regras, Stop, Testes

### Community 45 - "8. Fase 3 — Máquina de pipeline formal"
Cohesion: 0.29
Nodes (7): 8. Fase 3 — Máquina de pipeline formal, Compatibility mode, Engine, Formalização, Gate, Objetivo, Schema declarativo

### Community 46 - "9. Fase 4 — Confirmação semântica estruturada"
Cohesion: 0.29
Nodes (7): 9. Fase 4 — Confirmação semântica estruturada, Classificação sensível ao custo, Conformal set opcional, Gate, Objetivo, Regras, Saída do agente

### Community 47 - "required"
Cohesion: 0.29
Nodes (7): kind, suggested, task_id, tier, required, pipeline_id, source

### Community 48 - "type"
Cohesion: 0.29
Nodes (7): type, null, string, type, gate, phase, object

### Community 49 - "Verification Report — {Feature}"
Cohesion: 0.29
Nodes (6): Assumption audit, Boundaries and success metrics, Changed-path design coverage, Gaps and next decision, Requirement and AC coverage, Verification Report — {Feature}

### Community 50 - "Codex App Multitask State Implementation Plan"
Cohesion: 0.33
Nodes (5): Codex App Multitask State Implementation Plan, Task 1: State Scoping, Task 2: Owner-Aware Lock, Task 3: Observability, Task 4: Verification

### Community 51 - "7. Fase 2 — Endurecimento do state store"
Cohesion: 0.33
Nodes (6): 7. Fase 2 — Endurecimento do state store, Estratégia, Gate, Melhorias específicas, Schema, Testes

### Community 52 - "Harness4Codex implementation plan"
Cohesion: 0.40
Nodes (4): Harness4Codex implementation plan, Non-goals, Scope, Validation

### Community 53 - "5. Fase 0 — Linha de base e harness de teste do harness"
Cohesion: 0.40
Nodes (5): 5. Fase 0 — Linha de base e harness de teste do harness, Executor, Gate, Golden tests, Objetivo

### Community 54 - "6. Fase 1 — Observabilidade estruturada"
Cohesion: 0.40
Nodes (5): 6. Fase 1 — Observabilidade estruturada, Campos, Eventos, Gate, Regras

### Community 55 - "classification.schema.json"
Cohesion: 0.40
Nodes (4): additionalProperties, $id, $schema, type

### Community 56 - "risk_flags"
Cohesion: 0.40
Nodes (5): type, risk_flags, items, type, uniqueItems

### Community 57 - "enum"
Cohesion: 0.40
Nodes (5): L0, L1, L2, tier, enum

### Community 58 - "enum"
Cohesion: 0.40
Nodes (5): source, enum, human_override, regex, semantic

### Community 59 - "task-state.schema.json"
Cohesion: 0.40
Nodes (4): additionalProperties, $id, $schema, type

### Community 60 - "enum"
Cohesion: 0.40
Nodes (5): L0, L1, L2, tier, enum

### Community 61 - "16. Fase 11 — Process mining e melhoria orientada por dados"
Cohesion: 0.50
Nodes (4): 16. Fase 11 — Process mining e melhoria orientada por dados, Consolidação, Event log, Métricas

### Community 62 - "2. Princípio de otimização"
Cohesion: 0.50
Nodes (4): 2.1 Hard constraints, 2.2 Métricas otimizáveis, 2.3 Função, 2. Princípio de otimização

### Community 63 - "4. Artefatos obrigatórios antes da reforma"
Cohesion: 0.50
Nodes (4): 3.1 Preparação, 3.2 Proibições, 3.3 Stop conditions, 3. Regras de execução

### Community 82 - "__main__.py"
Cohesion: 0.33
Nodes (11): collect_graph_context(), _git_head(), _graph_head(), _latest_source_mtime(), Any, Path, _sha256(), write_graph_context() (+3 more)

### Community 83 - "Path"
Cohesion: 0.67
Nodes (3): revision, minimum, type

## Knowledge Gaps
- **334 isolated node(s):** `$schema`, `$id`, `type`, `branch_id`, `parent_session_id` (+329 more)
  These have ≤1 connection - possible missing edges or undocumented components.
- **20 thin communities (<3 nodes) omitted from report** — run `graphify query` to explore isolated nodes.

## Suggested Questions
_Questions this graph is uniquely positioned to answer:_

- **Why does `HarnessStateStore` connect `HarnessStateStore` to `hook.py`, `inspect_command`, `load_workflow`, `classify_prompt`?**
  _High betweenness centrality (0.061) - this node is a cross-community bridge._
- **Why does `HarnessDatabase` connect `load_workflow` to `HarnessStateStore`, `inspect_command`?**
  _High betweenness centrality (0.042) - this node is a cross-community bridge._
- **Why does `HarnessLiteClient` connect `cli.py` to `inspect_command`?**
  _High betweenness centrality (0.022) - this node is a cross-community bridge._
- **Are the 4 inferred relationships involving `HarnessDatabase` (e.g. with `BranchKeeper` and `BranchPolicyError`) actually correct?**
  _`HarnessDatabase` has 4 INFERRED edges - model-reasoned connections that need verification._
- **Are the 3 inferred relationships involving `HarnessStateStore` (e.g. with `Classification` and `ContractSnapshot`) actually correct?**
  _`HarnessStateStore` has 3 INFERRED edges - model-reasoned connections that need verification._
- **Are the 10 inferred relationships involving `StateTransitionError` (e.g. with `BranchKeeper` and `.offer()`) actually correct?**
  _`StateTransitionError` has 10 INFERRED edges - model-reasoned connections that need verification._
- **Are the 25 inferred relationships involving `_build_parser()` (e.g. with `_cmd_arsenal_check()` and `_cmd_arsenal_overlap()`) actually correct?**
  _`_build_parser()` has 25 INFERRED edges - model-reasoned connections that need verification._