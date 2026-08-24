# Graph Report - workflow-reliability  (2026-08-24)

## Corpus Check
- 42 files · ~16,696 words
- Verdict: corpus is large enough that graph structure adds value.

## Summary
- 461 nodes · 889 edges · 43 communities (38 shown, 5 thin omitted)
- Extraction: 98% EXTRACTED · 2% INFERRED · 0% AMBIGUOUS · INFERRED: 14 edges (avg confidence: 0.59)
- Token cost: 0 input · 0 output

## Graph Freshness
- Built from commit: `b4b46a61`
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
- 4. Artefatos obrigatórios antes da reforma

## God Nodes (most connected - your core abstractions)
1. `HarnessStateStore` - 44 edges
2. `handle_payload()` - 30 edges
3. `HarnessMemoryStore` - 27 edges
4. `classify_prompt()` - 16 edges
5. `build_task_envelope()` - 15 edges
6. `load_workflow()` - 14 edges
7. `Classification` - 13 edges
8. `store_for_payload()` - 13 edges
9. `_decode()` - 13 edges
10. `run_doctor()` - 12 edges

## Surprising Connections (you probably didn't know these)
- `test_status_prints_isolated_session_summary()` --calls--> `Classification`  [EXTRACTED]
  tests/test_cli.py → harness4codex/classifier.py
- `test_architecture_uses_design_and_review()` --calls--> `classify_prompt()`  [EXTRACTED]
  tests/test_classifier.py → harness4codex/classifier.py
- `test_bug_promotes_debugging_and_tdd()` --calls--> `classify_prompt()`  [EXTRACTED]
  tests/test_classifier.py → harness4codex/classifier.py
- `test_docs_sensitive_prompt_uses_docs_pipeline()` --calls--> `classify_prompt()`  [EXTRACTED]
  tests/test_classifier.py → harness4codex/classifier.py
- `test_feature_uses_light_spec_pipeline()` --calls--> `classify_prompt()`  [EXTRACTED]
  tests/test_classifier.py → harness4codex/classifier.py

## Import Cycles
- None detected.

## Communities (43 total, 5 thin omitted)

### Community 0 - "hook.py"
Cohesion: 0.12
Nodes (40): GuardDecision, inspect_command(), _append_lite_preview(), _append_science_context(), _append_workflow_context(), _block_stop(), _classification_context(), _command_from_payload() (+32 more)

### Community 1 - "cli.py"
Cohesion: 0.12
Nodes (28): build_task_envelope(), _canonical(), _digest(), evidence_bundle_is_acceptable(), execution_is_enabled(), git_base_revision(), HarnessLiteClient, lite_route_for() (+20 more)

### Community 2 - "HarnessStateStore"
Cohesion: 0.13
Nodes (23): Classification, default_harness_home(), default_state(), HarnessStateError, HarnessStateStore, list_session_states(), Path, PathLike (+15 more)

### Community 3 - "HarnessMemoryStore"
Cohesion: 0.17
Nodes (12): Connection, ConsolidationReport, HarnessMemoryStore, MemoryConsolidator, Any, Path, test_consolidator_creates_auditable_proposals_without_editing_files(), test_consolidator_reads_session_event_logs() (+4 more)

### Community 4 - "load_workflow"
Cohesion: 0.17
Nodes (15): find_workflow(), _indent_of(), load_workflow(), _parse_block(), _parse_limited_yaml(), _parse_scalar(), Any, Path (+7 more)

### Community 5 - "install"
Cohesion: 0.22
Nodes (18): _atomic_copytree(), build_hooks_config(), ensure_feature_flag(), _hook_entry(), _ignore_copy(), install(), main(), merge_hooks_config() (+10 more)

### Community 6 - "test_orchestration.py"
Cohesion: 0.24
Nodes (11): Issue, OrchestrationPolicy, Path, sanitize_workspace_key(), Workspace, WorkspaceManager, test_policy_allows_issue_when_blockers_terminal(), test_policy_blocks_issue_with_active_blocker() (+3 more)

### Community 7 - "classify_prompt"
Cohesion: 0.27
Nodes (12): classify_prompt(), _matches(), _normalize(), test_architecture_uses_design_and_review(), test_bug_promotes_debugging_and_tdd(), test_docs_sensitive_prompt_uses_docs_pipeline(), test_feature_uses_light_spec_pipeline(), test_openai_docs_prompt_uses_the_installed_openai_docs_skill() (+4 more)

### Community 8 - "run_doctor"
Cohesion: 0.32
Nodes (10): DiagnosticCheck, DoctorReport, _load_config(), Path, run_doctor(), _windows_user_environment(), test_doctor_accepts_one_supervisor_obsidian_and_science_mcp(), test_doctor_detects_competing_supervisor_and_disabled_required_apps() (+2 more)

### Community 9 - "PLANO_AUTOREFORMA_HARNESS4CODEX.md"
Cohesion: 0.20
Nodes (9): 0. Mandato, 17. Fase 12 — Otimização de hot paths, 1. Capacidades atuais que devem ser preservadas, 20. Critérios finais de aceitação, 21. Relatório final obrigatório, 22. Ordem resumida, Candidatos, Critério (+1 more)

### Community 10 - "10. Fase 5 — Graphify como fase nativa"
Cohesion: 0.20
Nodes (10): 10. Fase 5 — Graphify como fase nativa, Artefato, Atualização, Gate, Métricas, Novo step, Objetivo, Política por classe (+2 more)

### Community 11 - "inspect_command"
Cohesion: 0.19
Nodes (21): ArgumentParser, _build_parser(), _cmd_doctor(), _cmd_lite_preview(), _cmd_lite_submit(), _cmd_memory_consolidate(), _cmd_memory_search(), _cmd_status() (+13 more)

### Community 12 - "14. Fase 9 — Orquestração real"
Cohesion: 0.22
Nodes (9): 14. Fase 9 — Orquestração real, Advisory, Controlled, Etapas, Gate, Invariantes, Objetivo, Observe (+1 more)

### Community 13 - "Harness4Codex"
Cohesion: 0.22
Nodes (8): CLI, Codex App Multitask Safety, Harness4Codex, Install, Notes, Validate, What it adds, Workflow Policy

### Community 14 - "13. Fase 8 — Shell AST e policy engine"
Cohesion: 0.25
Nodes (8): 13. Fase 8 — Shell AST e policy engine, Decisões, Gate, Limites de `WORKFLOW.md`, Objetivo, OPA/Rego, Parser, Policy input

### Community 15 - "15. Fase 10 — Testes avançados"
Cohesion: 0.25
Nodes (8): 15. Fase 10 — Testes avançados, Classificador, Concurrency, Memória, Metamorphic, Mutation testing, Property-based, Workflow

### Community 16 - "18. Fase 13 — Canário e rollout"
Cohesion: 0.25
Nodes (8): 18. Fase 13 — Canário e rollout, C0, C1, C2/C3, CR/DOCS, Fixtures, Rollback, Shadow

### Community 17 - "19. Protocolo de comparação com Harness4Claude"
Cohesion: 0.25
Nodes (8): 19. Protocolo de comparação com Harness4Claude, Corpus, Hard constraints, Performance, Qualidade, Restrições, Resultado, Transferência

### Community 18 - "Symphony Memory Workflow Implementation Plan"
Cohesion: 0.29
Nodes (6): Symphony Memory Workflow Implementation Plan, Task 1: Workflow Loader, Task 2: SQLite Memory And Consolidation, Task 3: CLI Status Surface, Task 4: Orchestration Primitives, Task 5: Install, Verify, Commit, Push

### Community 19 - "Symphony Memory Workflow Design"
Cohesion: 0.29
Nodes (6): Architecture, Context, Goals, Non-Goals, Safety, Symphony Memory Workflow Design

### Community 20 - "science_context"
Cohesion: 0.67
Nodes (5): _normalize(), science_context(), wants_science_evidence(), test_ordinary_bugfix_does_not_activate_science_route(), test_scientific_evidence_prompts_activate_the_read_only_mcp_route()

### Community 21 - "11. Fase 6 — Índice gráfico e recuperação"
Cohesion: 0.29
Nodes (7): 11. Fase 6 — Índice gráfico e recuperação, Depois: ranking local, Gate, Graph sidecar, GraphBLAS, HNSW, Primeiro: FTS5

### Community 22 - "12. Fase 7 — Evidência forte e Stop gate"
Cohesion: 0.29
Nodes (7): 12. Fase 7 — Evidência forte e Stop gate, Evidência mínima, Gate, Objetivo, Regras, Stop, Testes

### Community 23 - "8. Fase 3 — Máquina de pipeline formal"
Cohesion: 0.29
Nodes (7): 8. Fase 3 — Máquina de pipeline formal, Compatibility mode, Engine, Formalização, Gate, Objetivo, Schema declarativo

### Community 24 - "9. Fase 4 — Confirmação semântica estruturada"
Cohesion: 0.29
Nodes (7): 9. Fase 4 — Confirmação semântica estruturada, Classificação sensível ao custo, Conformal set opcional, Gate, Objetivo, Regras, Saída do agente

### Community 25 - "Codex App Multitask State Implementation Plan"
Cohesion: 0.33
Nodes (5): Codex App Multitask State Implementation Plan, Task 1: State Scoping, Task 2: Owner-Aware Lock, Task 3: Observability, Task 4: Verification

### Community 26 - "7. Fase 2 — Endurecimento do state store"
Cohesion: 0.33
Nodes (6): 7. Fase 2 — Endurecimento do state store, Estratégia, Gate, Melhorias específicas, Schema, Testes

### Community 27 - "Codex Harness Workflow"
Cohesion: 0.33
Nodes (5): Capability Routing, Codex Harness Workflow, Core Rules, Pipeline Map, Stop Gate

### Community 29 - "Harness4Codex implementation plan"
Cohesion: 0.40
Nodes (4): Harness4Codex implementation plan, Non-goals, Scope, Validation

### Community 30 - "5. Fase 0 — Linha de base e harness de teste do harness"
Cohesion: 0.40
Nodes (5): 5. Fase 0 — Linha de base e harness de teste do harness, Executor, Gate, Golden tests, Objetivo

### Community 31 - "6. Fase 1 — Observabilidade estruturada"
Cohesion: 0.40
Nodes (5): 6. Fase 1 — Observabilidade estruturada, Campos, Eventos, Gate, Regras

### Community 32 - "16. Fase 11 — Process mining e melhoria orientada por dados"
Cohesion: 0.50
Nodes (4): 16. Fase 11 — Process mining e melhoria orientada por dados, Consolidação, Event log, Métricas

### Community 33 - "2. Princípio de otimização"
Cohesion: 0.50
Nodes (4): 2.1 Hard constraints, 2.2 Métricas otimizáveis, 2.3 Função, 2. Princípio de otimização

### Community 34 - "3. Regras de execução"
Cohesion: 0.50
Nodes (4): 3.1 Preparação, 3.2 Proibições, 3.3 Stop conditions, 3. Regras de execução

### Community 35 - "17. Fase 12 — Otimização de hot paths"
Cohesion: 0.23
Nodes (20): handle_payload(), Path, _decode(), test_parallel_sessions_do_not_continue_each_other(), test_permission_request_denies_dangerous_git(), test_permission_request_warning_uses_only_a_generic_system_message(), test_post_tool_use_promotes_after_multiple_files(), test_pre_tool_use_denies_dangerous_git() (+12 more)

### Community 42 - "4. Artefatos obrigatórios antes da reforma"
Cohesion: 0.50
Nodes (4): 4.1 Inventário, 4.2 Baseline, 4.3 Replays, 4. Artefatos obrigatórios antes da reforma

## Knowledge Gaps
- **130 isolated node(s):** `harness4codex`, `install.sh script`, `0. Mandato`, `1. Capacidades atuais que devem ser preservadas`, `2.1 Hard constraints` (+125 more)
  These have ≤1 connection - possible missing edges or undocumented components.
- **5 thin communities (<3 nodes) omitted from report** — run `graphify query` to explore isolated nodes.

## Suggested Questions
_Questions this graph is uniquely positioned to answer:_

- **Why does `HarnessStateStore` connect `HarnessStateStore` to `hook.py`, `17. Fase 12 — Otimização de hot paths`, `inspect_command`?**
  _High betweenness centrality (0.066) - this node is a cross-community bridge._
- **Why does `HarnessMemoryStore` connect `HarnessMemoryStore` to `hook.py`, `17. Fase 12 — Otimização de hot paths`, `inspect_command`?**
  _High betweenness centrality (0.047) - this node is a cross-community bridge._
- **Why does `build_task_envelope()` connect `cli.py` to `inspect_command`?**
  _High betweenness centrality (0.042) - this node is a cross-community bridge._
- **What connects `harness4codex`, `install.sh script`, `0. Mandato` to the rest of the system?**
  _130 weakly-connected nodes found - possible documentation gaps or missing edges._
- **Should `hook.py` be split into smaller, more focused modules?**
  _Cohesion score 0.11733615221987315 - nodes in this community are weakly interconnected._
- **Should `cli.py` be split into smaller, more focused modules?**
  _Cohesion score 0.12063492063492064 - nodes in this community are weakly interconnected._
- **Should `HarnessStateStore` be split into smaller, more focused modules?**
  _Cohesion score 0.13360323886639677 - nodes in this community are weakly interconnected._