---
title: Plano de Autorreforma Segura e Otimização Máxima — Harness4Codex
system: Harness4Codex
document_type: execution-plan
status: ready-for-execution
version: 1.0
created: 2026-07-23
owner: Harness4Codex
comparison_peer: Harness4Claude
priority: safety-first-performance
---

# Plano de Autorreforma Segura e Otimização Máxima — Harness4Codex

## 0. Mandato

Este documento deve ser executado pelo próprio **Harness4Codex** no repositório que contém seus hooks, classificador, store de estado, memória, guardrails, workflow parser e primitivas de orquestração.

O objetivo é elevar o sistema de uma coordenação híbrida — parcialmente determinística e parcialmente instrucional — para uma coordenação em que:

- classificação;
- fases;
- obrigações;
- artefatos;
- evidências;
- transições;
- segurança;
- encerramento;
- atualização de grafo;
- auditoria;

sejam formalmente verificáveis pelo núcleo do harness, sem remover a flexibilidade do agente para raciocinar, implementar e escolher técnicas.

A reforma deve preservar a principal vantagem atual do Harness4Codex: **isolamento lógico por `session_id + cwd`**, combinado com lock de propriedade e escrita atômica.

A mudança deve ser gradual, reversível e mensurada. Nenhuma otimização pode enfraquecer o Stop gate, o Git guard, o isolamento entre scopes ou a recuperabilidade do estado.

---

# 1. Capacidades atuais que devem ser preservadas

- hooks para eventos do Codex;
- classificação C0, C1, C2, C3, CR e DOCS;
- normalização de texto;
- state escopado;
- `events.jsonl`;
- `errors.log`;
- lock por diretório;
- owner token;
- stale cleanup;
- `os.replace`;
- promoção por arquivos distintos;
- reconhecimento positivo de verificações;
- Stop gate;
- parser limitado de `WORKFLOW.md`;
- segurança Git;
- memória SQLite;
- consolidação em propostas;
- backoff;
- primitivas `Issue`, `WorkspaceManager` e elegibilidade;
- comportamento fail-soft da memória auxiliar;
- idempotência das propostas.

Riscos prioritários:

1. `current_step` não comprova que a fase foi executada;
2. artefatos não são obrigações transacionais;
3. verificação depende principalmente de catálogo de comando e exit code;
4. o agente precisa ler e obedecer ao output para completar enforcement;
5. Graphify não é fase nativa do state machine;
6. confirmação semântica não está incorporada como decisão estruturada;
7. memória usa busca textual simples;
8. regex de shell não entende AST;
9. `orchestration.py` ainda está desacoplado;
10. o lock atual não usa fencing monotônico;
11. a política local precisa de limites de capability mais explícitos.

---

# 2. Princípio de otimização

A otimização será feita por hard constraints e fronteira de Pareto.

## 2.1 Hard constraints

Uma versão é rejeitada se ocorrer:

- perda de isolamento;
- corrupção de state;
- lost update;
- bypass do Git guard;
- conclusão sem evidência;
- artefato de task errada satisfazendo gate;
- lock antigo escrevendo;
- regressão de testes;
- rollback impossível;
- Graphify vazando arquivo ignorado;
- política local enfraquecendo regra global.

## 2.2 Métricas otimizáveis

Depois dos hard constraints:

- latência de hooks;
- throughput;
- tempo de classificação;
- tempo de busca de memória;
- tempo de Graphify;
- número de arquivos abertos;
- tokens/contexto;
- tempo de verificação;
- CPU;
- memória;
- I/O;
- quantidade de retries;
- taxa de retrabalho;
- complexidade operacional.

## 2.3 Função

\[
J =
w_l L_n +
w_t T_n +
w_c C_n +
w_i I_n +
w_r R_n
\]

Os pesos devem ser congelados antes do benchmark final.

---

# 3. Regras de execução

## 3.1 Preparação

- branch dedicada;
- worktree dedicado;
- commit-base;
- tag local;
- export dos stores por scope;
- backup de memória SQLite;
- backup de `WORKFLOW.md` de fixtures;
- cópia dos hooks;
- inventário de versões;
- repositório limpo;
- nenhum rollout global antes do canário.

Estrutura:

```text
docs/self-reform/codex/
  INVENTORY.md
  BASELINE.md
  RISK_REGISTER.md
  ARCHITECTURE.md
  ADR/
  PIPELINE_SCHEMA.md
  GRAPH_CONTEXT_SCHEMA.md
  EVIDENCE_SCHEMA.md
  TEST_MATRIX.md
  MIGRATION_LOG.md
  PERFORMANCE_REPORT.md
  VALIDATION_REPORT.md
  ROLLBACK_REPORT.md
  CROSS_COMPARISON.md
```

## 3.2 Proibições

- não apagar stores legados;
- não converter todos os scopes de uma vez;
- não tornar Graphify obrigatório para toda tarefa;
- não adicionar dependência pesada sem benchmark;
- não confiar em classificação sem registrar origem;
- não aceitar exit code como prova suficiente para classes de maior risco;
- não permitir edição direta do novo store;
- não modificar o Harness4Claude durante a reforma;
- não habilitar OPA, GraphBLAS, HNSW ou processo persistente sem necessidade demonstrada;
- não fazer tuning antes de completar testes de integridade.

## 3.3 Stop conditions

- divergência não explicada entre store legado e novo;
- perda de evento;
- estado de outro scope;
- verificação atribuída ao commit errado;
- transição sem artefato;
- loop de Stop;
- aumento de falso bloqueio;
- deadlock;
- starvation;
- graph update modificando arquivos inesperados;
- política local ampliando permissões;
- benchmark não reproduzível.

---

# 4. Artefatos obrigatórios antes da reforma

## 4.1 Inventário

Mapear:

- cada hook;
- cada payload;
- cada adaptador;
- campos possíveis de exit code;
- funções do classificador;
- funções de state;
- lock acquisition/release;
- stale cleanup;
- promoção;
- verificação;
- Stop;
- memória;
- consolidação;
- parser;
- Git guard;
- orchestration;
- referências a Graphify;
- regras de `AGENTS.md`;
- regras de `WORKFLOW.md`;
- pontos de escrita.

## 4.2 Baseline

Medir:

- p50/p95/p99 por hook;
- tempo de startup;
- classificação;
- state read/write;
- lock wait;
- Stop;
- busca `LIKE`;
- memória com 100, 1.000, 10.000 e 100.000 registros;
- tasks por segundo;
- sessões concorrentes;
- crash durante escrita;
- lock stale;
- JSON corrompido;
- verificação;
- promoção por arquivo;
- custo de Graphify manual;
- arquivos abertos sem Graphify;
- tokens/contexto;
- taxa de underclassification;
- taxa de overclassification;
- taxa de Stop bloqueado;
- falsos positivos Git;
- falsos negativos Git.

## 4.3 Replays

Criar logs reproduzíveis de:

- C0;
- C1;
- C2;
- C3;
- CR;
- DOCS;
- prompts ambíguos;
- prompts bilíngues;
- 2/4/8/16 sessões;
- alteração em um arquivo;
- alteração em três;
- verificação válida;
- comando parecido, mas inválido;
- exit code em diferentes campos;
- conclusão prematura;
- restart;
- worktree;
- Graphify stale.

---

# 5. Fase 0 — Linha de base e harness de teste do harness

## Objetivo

Criar um executor determinístico de eventos para testar o próprio sistema.

## Executor

O test harness deve:

- carregar fixture;
- enviar evento;
- capturar stdout/stderr;
- capturar exit code;
- capturar diff do store;
- capturar eventos;
- capturar logs;
- validar schema;
- medir duração;
- permitir kill em pontos definidos;
- executar múltiplos workers;
- reproduzir seed.

## Golden tests

Salvar resultados esperados do sistema atual para:

- classificação;
- scope;
- promoção;
- verificação;
- Stop;
- Git guard;
- parser;
- memória;
- consolidação.

Golden tests não significam que o comportamento atual está correto; servem para identificar mudanças deliberadas.

## Gate

- replay determinístico;
- baseline repetível;
- todos os testes atuais passam;
- nenhuma reforma estrutural ativa.

---

# 6. Fase 1 — Observabilidade estruturada

## Eventos

Adicionar:

```text
hook_received
scope_resolved
classification_suggested
classification_confirmed
classification_overridden
task_loaded
lease_acquired
transition_requested
transition_rejected
artifact_recorded
evidence_recorded
verification_evaluated
graph_context_started
graph_context_completed
stop_evaluated
task_finished
rollback_started
rollback_completed
```

## Campos

```text
event_version
task_id
scope_id
session_id_hash
cwd_hash
worktree_hash
sequence
revision
owner_epoch
duration_ms
result
reason_code
```

## Regras

- não registrar prompt integral por padrão;
- redaction;
- hash para campos sensíveis;
- schema versionado;
- telemetria falha sem afetar state;
- eventos ordenados por task;
- relógio monotônico para duração.

## Gate

- overhead conhecido;
- log reconstrói task;
- nenhuma informação sensível sintética vaza.

---

# 7. Fase 2 — Endurecimento do state store

O Harness4Codex já tem isolamento por scope. A reforma deve preservá-lo e fortalecer a integridade física.

## Estratégia

Migrar gradualmente:

```text
state.json + events.jsonl
→ SQLite shadow
→ dual-write
→ SQLite primary
→ legado read-only
```

## Schema

```sql
CREATE TABLE scopes (
  scope_id TEXT PRIMARY KEY,
  session_fingerprint TEXT,
  cwd TEXT NOT NULL,
  worktree_root TEXT,
  repository_id TEXT,
  created_at TEXT NOT NULL
);

CREATE TABLE tasks (
  task_id TEXT PRIMARY KEY,
  scope_id TEXT NOT NULL,
  status TEXT NOT NULL,
  class TEXT NOT NULL,
  current_step TEXT,
  revision INTEGER NOT NULL,
  owner_epoch INTEGER NOT NULL,
  verified INTEGER NOT NULL DEFAULT 0,
  created_at TEXT NOT NULL,
  updated_at TEXT NOT NULL
);

CREATE UNIQUE INDEX one_active_task_per_scope
ON tasks(scope_id)
WHERE status = 'active';

CREATE TABLE events (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  task_id TEXT NOT NULL,
  seq INTEGER NOT NULL,
  type TEXT NOT NULL,
  payload_json TEXT NOT NULL,
  created_at TEXT NOT NULL,
  UNIQUE(task_id, seq)
);

CREATE TABLE files (
  task_id TEXT NOT NULL,
  normalized_path TEXT NOT NULL,
  first_seen_event INTEGER,
  PRIMARY KEY(task_id, normalized_path)
);

CREATE TABLE artifacts (
  task_id TEXT NOT NULL,
  artifact_type TEXT NOT NULL,
  path TEXT NOT NULL,
  hash TEXT,
  step TEXT,
  PRIMARY KEY(task_id, artifact_type, path)
);

CREATE TABLE evidence (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  task_id TEXT NOT NULL,
  evidence_type TEXT NOT NULL,
  command_ast_json TEXT,
  exit_code INTEGER,
  output_hash TEXT,
  repository_head TEXT,
  working_tree_hash TEXT,
  created_at TEXT NOT NULL
);

CREATE TABLE leases (
  scope_id TEXT PRIMARY KEY,
  owner_token TEXT NOT NULL,
  owner_epoch INTEGER NOT NULL,
  heartbeat_at TEXT NOT NULL,
  expires_at TEXT NOT NULL
);
```

## Melhorias específicas

- substituir lista de paths por tabela com chave primária;
- eliminar busca O(|F|);
- revision CAS;
- fencing token;
- short transactions;
- WAL;
- backup;
- migrations;
- integrity check;
- checkpoint controlado;
- busy timeout;
- nenhuma ferramenta externa em transação.

## Testes

- 100.000 paths duplicados;
- 10.000 scopes;
- 16 writers;
- kill;
- disk full;
- permission denied;
- backup/restore;
- migration interrupted;
- stale process return.

## Gate

- nenhuma colisão lógica;
- nenhum lost update;
- state read performance igual ou superior;
- files distinct em O(log n) ou melhor via índice;
- rollback testado.

---

# 8. Fase 3 — Máquina de pipeline formal

## Objetivo

Fazer com que o core valide o pipeline, em vez de apenas instruir o agente.

## Schema declarativo

```yaml
pipeline: C3
version: 1
initial: classified
terminal:
  - done
  - abandoned
  - rolled_back

steps:
  classified:
    next:
      - graph_context

  graph_context:
    requires:
      - graph_context.json
    next:
      - specification

  specification:
    produces:
      - spec.md
    next:
      - design

  design:
    produces:
      - design.md
    next:
      - implementation

  implementation:
    produces:
      - changed_files
    next:
      - verification

  verification:
    requires:
      - test_evidence
      - graph_update_evidence
    next:
      - done
```

## Engine

A transição deve validar:

- classe;
- step atual;
- next permitido;
- artifact obligations;
- evidence obligations;
- repository revision;
- scope;
- owner epoch;
- retries;
- timeouts;
- human gate;
- exception documentada.

## Compatibility mode

- `advisory`: apenas registra divergências;
- `enforced-low-risk`: bloqueia em fixtures e C0;
- `enforced`: aplica por classes;
- feature flag por scope.

## Formalização

Especificar em TLA+/PlusCal:

- duas tasks;
- dois scopes;
- transições;
- lease;
- stale owner;
- verify;
- Stop;
- continuation única;
- retry;
- done.

Invariantes:

```text
OneActiveTaskPerScope
NoCrossScope
NoPrematureDone
VerificationMatchesRevision
ArtifactMatchesTask
OnlyOwnerTransitions
RevisionMonotonic
ContinuationBounded
TerminalStable
```

## Gate

- model checker sem contraexemplo no modelo;
- engine e modelo possuem mapeamento documentado;
- todos os pipelines têm schema;
- comportamento legado comparado por replay.

---

# 9. Fase 4 — Confirmação semântica estruturada

## Objetivo

Combinar velocidade determinística com revisão semântica explícita.

## Saída do agente

```json
{
  "suggested_class": "C2",
  "confirmed_class": "C3",
  "confidence": 0.84,
  "reason_codes": [
    "cross_module_change",
    "architecture_decision"
  ],
  "expected_artifacts": [
    "spec",
    "design",
    "verification"
  ],
  "expected_scope": {
    "files": "multi",
    "components": 3
  }
}
```

## Regras

- resposta precisa validar schema;
- classificação confirmada recebe provenance;
- override humano é separado;
- confirmação não pode reduzir classe crítica sem justificativa;
- promoção por cardinalidade permanece como sinal, não verdade absoluta;
- divergências alimentam métricas.

## Classificação sensível ao custo

Penalizar underclassification mais que overclassification.

Registrar matriz de custo e congelá-la antes de avaliação.

## Conformal set opcional

Somente após dataset suficiente:

```text
{C2}
{C2, C3}
```

Quando conjunto contém classe de maior risco, escolher abordagem conservadora.

## Gate

- underclassification reduzida;
- overhead aceitável;
- fallback determinístico;
- nenhum prompt de ferramenta influencia intenção humana.

---

# 10. Fase 5 — Graphify como fase nativa

## Objetivo

Integrar o grafo ao state machine, não apenas ao `AGENTS.md`.

## Novo step

```text
graph_context_required
graph_context_running
graph_context_complete
graph_context_exception
```

## Artefato

`graph-context.json`:

```json
{
  "schema_version": 1,
  "task_id": "...",
  "scope_id": "...",
  "repository_head": "...",
  "graph_head": "...",
  "graphify_version": "...",
  "manifest_hash": "...",
  "freshness": "fresh",
  "queries": [
    {
      "mode": "query",
      "text_hash": "...",
      "returned_nodes": [],
      "returned_communities": [],
      "candidate_files": [],
      "duration_ms": 0
    }
  ],
  "exceptions": []
}
```

## Política por classe

- C0: Graphify opcional;
- C1: recomendado quando codebase desconhecida;
- C2: obrigatório salvo exceção;
- C3: obrigatório;
- CR: obrigatório quando relação entre componentes é relevante;
- DOCS: opcional conforme fonte.

## Upgrade seguro

- instalar Graphify candidato isolado;
- testar comandos realmente disponíveis;
- comparar grafo;
- testar ignores;
- testar update incremental;
- pin;
- canário;
- rollback.

## Atualização

Depois de mudanças:

- update incremental;
- registrar HEAD;
- registrar manifest;
- comparar se nós alterados correspondem aos arquivos;
- não marcar task verificada se graph update obrigatório falhar, salvo exceção formal.

## Query planner

```text
classificação
→ intenção
→ comunidades candidatas
→ query/path/explain
→ arquivos candidatos
→ abertura seletiva
```

## Métricas

- files-opened reduction;
- token reduction;
- graph query latency;
- graph stale rate;
- candidate precision;
- dependency recall;
- graph update cost;
- fallback rate.

## Gate

- fase nativa funcionando;
- artefato validado;
- Graphify não bloqueia C0 indevidamente;
- C2/C3 não pulam contexto sem exceção registrada;
- nenhum segredo indexado.

---

# 11. Fase 6 — Índice gráfico e recuperação

## Primeiro: FTS5

A memória atual deve migrar de `LIKE` para FTS5/BM25, mantendo filtros estruturados.

Tabelas:

```text
memory_events
memory_fts
artifact_fts
proposal_fts
```

Triggers ou processo explícito devem manter o índice consistente.

## Depois: ranking local

Implementar ranking híbrido:

\[
Score =
w_t Text
+w_p Proximity
+w_c Community
+w_e Evidence
-w_h Hub
-w_s Staleness
\]

## Graph sidecar

Manter `graph.json` canônico e criar índices laterais:

```text
graphify-out/
  graph.json
  graph.index.sqlite
  graph.ast.bin
  graph.semantic.bin
  retrieval-manifest.json
```

## HNSW

Somente se:

- busca textual não recuperar conceitos;
- corpus for grande;
- custo for justificado;
- recall for medido.

HNSW gera candidatos; não decide relação estrutural.

## GraphBLAS

Somente se:

- grafo grande;
- algoritmos em lote dominarem o tempo;
- benchmark mostrar ganho real;
- complexidade de build for aceitável.

## Gate

- FTS5 reduz latência significativamente no corpus;
- ranking não perde casos críticos;
- índices são reconstruíveis;
- fallback para `graph.json`;
- provenance presente.

---

# 12. Fase 7 — Evidência forte e Stop gate

## Objetivo

Substituir o booleano simples de verificação por um conjunto de evidências ligado à revisão exata do código.

## Evidência mínima

```json
{
  "task_id": "...",
  "repository_head": "...",
  "working_tree_hash": "...",
  "command": "...",
  "command_ast": {},
  "catalog_match": true,
  "exit_code": 0,
  "started_at": "...",
  "finished_at": "...",
  "output_hash": "...",
  "tests_collected": 0,
  "tests_passed": 0,
  "coverage_reference": null
}
```

## Regras

- exit 0 sem testes coletados pode não valer;
- evidência expira quando o código muda;
- verificação de outro scope não vale;
- comando não reconhecido não vira evidência automaticamente;
- classes C2/C3 exigem múltiplas dimensões;
- Graphify update pode ser obrigação;
- artefatos devem existir e ter hash.

## Stop

```text
block_stop =
active
AND pipeline_requires_work
AND NOT obligations_satisfied
AND continuation_budget_available
```

Se budget acabou, não liberar silenciosamente: registrar estado de falha controlada e instrução explícita.

## Testes

- exit 0 com zero testes;
- teste antes de modificar código;
- código muda após teste;
- output truncado;
- exit code em campo inesperado;
- comando wrapper;
- comando que contém palavra `pytest` mas não executa;
- duas verificações concorrentes;
- evidence de outra task.

## Gate

- nenhuma conclusão prematura;
- loops controlados;
- evidência ligada à revisão;
- falsos bloqueios medidos.

---

# 13. Fase 8 — Shell AST e policy engine

## Objetivo

Fortalecer Git guard e políticas locais.

## Parser

Usar parser de shell incremental quando suportado.

Pipeline:

```text
raw command
→ shell parse
→ command normalization
→ policy input
→ decision
```

## Policy input

```json
{
  "program": "git",
  "subcommand": "reset",
  "flags": ["--hard"],
  "paths": [],
  "wrappers": [],
  "scope": "...",
  "repository": "...",
  "source": "PreToolUse"
}
```

## Decisões

```text
allow
warn
require_approval
deny
unknown
```

`unknown` deve ser seguro e observável.

## Limites de `WORKFLOW.md`

O documento local pode:

- exigir verificações adicionais;
- declarar comandos permitidos;
- declarar artefatos;
- definir estados locais;
- aumentar rigor.

Não pode:

- permitir força destrutiva;
- remover verificação;
- dispensar artefato global;
- ignorar scope;
- alterar owner;
- declarar task done;
- reduzir classe de segurança.

## OPA/Rego

Adotar apenas se:

- política crescer além de capacidade segura do código local;
- overhead for aceitável;
- testes de policy forem mantidos;
- fallback estiver disponível.

## Gate

- corpus adversarial sem bypass;
- falsos positivos aceitáveis;
- regras globais não enfraquecidas;
- parser failure tratado.

---

# 14. Fase 9 — Orquestração real

## Objetivo

Integrar `orchestration.py` ao runtime sem introduzir automação agressiva.

## Etapas

### Observe

- calcular elegibilidade;
- calcular backoff;
- não executar;
- comparar decisões.

### Advisory

- sugerir workspace/worktree;
- sugerir retry;
- registrar.

### Controlled

- executar somente em fixtures;
- limites de concorrência;
- quotas;
- cancelamento;
- timeout.

### Production

- somente tarefas explicitamente elegíveis;
- ownership;
- heartbeats;
- retries idempotentes;
- cleanup;
- evidência.

## Invariantes

```text
Issue pertence a uma task
Workspace pertence a um scope
Retry não duplica efeitos
Backoff tem teto
Cancelamento encerra workers
Task terminal não recebe novo worker
```

## Gate

- testes de concorrência;
- nenhuma duplicação;
- cleanup completo;
- backoff medido;
- rollout por feature flag.

---

# 15. Fase 10 — Testes avançados

## Property-based

- scope determinístico;
- paths distintos;
- revision monotônica;
- transição idempotente;
- owner antigo rejeitado;
- verificação expira após alteração;
- parser não aceita estrutura proibida;
- propostas continuam idempotentes.

## Metamorphic

### Classificador

- acentos;
- caixa;
- whitespace;
- tradução;
- conteúdo de ferramenta;
- reordenação de frases;
- paths duplicados.

### Workflow

- ordem de eventos independentes não afeta scopes;
- replay produz mesmo state;
- rebuild total e update incremental convergem;
- retry após crash aplica uma vez.

### Memória

- inserir mesma proposta duas vezes não duplica;
- FTS5 e busca exata concordam em casos exatos;
- filtros por scope nunca retornam outro scope.

## Mutation testing

Mutantes críticos:

- remover `exit_code == 0`;
- remover owner token;
- remover revision CAS;
- permitir DONE sem artefato;
- ignorar Graphify stale;
- aceitar `--force-with-lease`;
- confundir `session_id`;
- contar path duplicado;
- aceitar evidence antiga.

Mutation score crítico deve ser 100%.

## Concurrency

- 2/4/8/16 workers;
- 10.000 eventos;
- kill aleatório;
- stale lease;
- writer starvation;
- checkpoint;
- backup;
- disk full.

---

# 16. Fase 11 — Process mining e melhoria orientada por dados

## Event log

```text
case_id
activity
timestamp
scope
class
pipeline
step_from
step_to
result
reason
duration
artifact
evidence
```

## Métricas

- fitness;
- precision;
- skipped steps;
- rework;
- retries;
- Stop blocks;
- completion rate;
- underclassification;
- overclassification;
- Graphify hit rate;
- files opened;
- token compression;
- verification yield;
- false blockers;
- escaped defects.

## Consolidação

O consolidator pode gerar propostas com base em padrões, mas:

- não muda política automaticamente;
- proposta inclui evidência;
- proposta inclui impacto;
- proposta inclui rollback;
- proposta é revisável;
- chave idempotente permanece.

---

# 17. Fase 12 — Otimização de hot paths

Somente depois da integridade.

## Candidatos

- cache de regex compilada;
- cache de WORKFLOW por hash;
- prepared statements;
- FTS5;
- batch de eventos;
- reduzir serialização JSON repetida;
- evitar abrir arquivos desnecessários;
- carregar state mínimo;
- limitar subprocessos;
- lazy Graphify;
- graph community pruning;
- cache frio/quente separado;
- processo persistente apenas se lifecycle seguro;
- reduzir polling;
- usar notificações quando viável;
- checkpoint WAL controlado.

## Critério

Cada otimização precisa de benchmark A/B e rollback.

Não aceitar “micro-otimização” que aumente complexidade sem ganho material.

---

# 18. Fase 13 — Canário e rollout

## Shadow

- novo engine observa;
- legado decide;
- divergências registradas.

## Fixtures

- novo engine decide em repositórios descartáveis.

## C0

- tarefas simples;
- Graphify opcional;
- monitorar.

## C1

- bugs;
- evidência mais forte.

## C2/C3

- somente após gates anteriores;
- Graphify nativo;
- artefatos;
- verificação multidimensional.

## CR/DOCS

- regras específicas;
- validar custo.

## Rollback

- feature flag;
- legado preservado;
- migration down;
- backup;
- restore drill;
- documentação.

---

# 19. Protocolo de comparação com Harness4Claude

## Restrições

- nenhuma escrita no repositório do outro;
- mesma máquina;
- mesmo corpus;
- mesmas repetições;
- mesmas versões auxiliares quando possível;
- raw data preservado;
- caches frios e quentes separados;
- não alterar parâmetros depois de ver resultados.

## Corpus

1. C0/L0;
2. bug;
3. refactor;
4. architecture;
5. feature;
6. review;
7. docs;
8. prompt ambíguo;
9. prompt bilíngue;
10. prompt longo;
11. duas sessões;
12. oito sessões;
13. crash;
14. stale lock;
15. Graphify stale;
16. Graphify update;
17. comando Git adversarial;
18. artifact missing;
19. exit 0 sem teste;
20. rollback.

## Hard constraints

- invariantes;
- cross-scope;
- lost update;
- premature done;
- Git bypass;
- rollback;
- corrupção;
- stale owner.

Uma falha elimina a versão daquela comparação.

## Performance

- p50/p95/p99;
- throughput;
- startup;
- state operations;
- classification;
- Graphify;
- memory search;
- CPU;
- RAM;
- I/O;
- tokens;
- files opened;
- verification time;
- recovery.

## Qualidade

- classificação;
- underclassification;
- overclassification;
- artifacts;
- evidence;
- findings;
- false blockers;
- escaped defects;
- conformance;
- explicabilidade.

## Resultado

Criar:

```text
docs/self-reform/codex/CROSS_COMPARISON.md
docs/self-reform/codex/cross-comparison-results.json
docs/self-reform/codex/raw-benchmarks/
```

Declarar vencedor por dimensão. Não distorcer para obter vencedor único.

## Transferência

Toda técnica do Claude considerada superior deve virar proposta separada com:

- motivação;
- compatibilidade;
- custo;
- risco;
- teste;
- rollback.

---

# 20. Critérios finais de aceitação

- [ ] isolamento por scope preservado;
- [ ] state transacional validado;
- [ ] fencing token implementado;
- [ ] paths distintos indexados;
- [ ] pipeline formal ativo;
- [ ] artefatos validados;
- [ ] evidência ligada ao código;
- [ ] Stop não depende apenas de exit code;
- [ ] Graphify é fase nativa onde exigido;
- [ ] Graphify tem freshness e provenance;
- [ ] FTS5 substitui busca inadequada;
- [ ] classificação semântica estruturada;
- [ ] Git guard usa parsing robusto ou dual-mode validado;
- [ ] `WORKFLOW.md` não reduz segurança global;
- [ ] orchestration integrada com controle;
- [ ] property-based tests passam;
- [ ] metamorphic tests passam;
- [ ] mutation score crítico é 100%;
- [ ] model checking sem contraexemplo no modelo;
- [ ] conformance registrada;
- [ ] performance melhor ou não inferior dentro do orçamento;
- [ ] rollback completo executado;
- [ ] comparação com Claude concluída;
- [ ] documentação atualizada;
- [ ] versão pinada e reproduzível.

---

# 21. Relatório final obrigatório

```markdown
# Relatório Final — Harness4Codex

## Estado inicial
## Estado final
## Commits
## Arquitetura
## Store
## Pipeline formal
## Classificação
## Graphify
## Memória
## Evidência
## Segurança
## Orquestração
## Testes
## Model checking
## Process mining
## Performance
## Rollback
## Limitações
## Comparação com Harness4Claude
## Decisão de rollout
```

Cada conclusão deve apontar para dados ou testes.

---

# 22. Ordem resumida

```text
inventário
→ baseline
→ observabilidade
→ SQLite shadow
→ dual-write
→ fencing/revision
→ pipeline formal
→ confirmação semântica
→ Graphify nativo
→ FTS5/ranking
→ evidence gate
→ shell AST/policy
→ orchestration controlada
→ testes formais
→ process mining
→ tuning
→ canário
→ rollback drill
→ comparação com Claude
→ rollout
```

Não iniciar GraphBLAS, HNSW ou automação adaptativa antes de demonstrar que FTS5, bons índices e query planning simples são insuficientes.
