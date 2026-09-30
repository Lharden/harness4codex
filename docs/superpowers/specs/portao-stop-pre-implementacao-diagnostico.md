# Portão de Stop antes da implementação — diagnóstico (harness4codex)

Ramo `fix/portao-stop-pre-implementacao`, base `main` em `4ec4047`. Pipeline
L2-bug conduzida a partir da sessão harness4claude `790d2b9a`
(task `t-20260930-145319810090`).

Referência de conserto: harness4claude, ramo `claude/cool-lichterman-5718b9`,
`docs/specs/portao-stop-pre-implementacao-diagnostico.md` (regra
`cobra_evidencia_nesta_fase`, decisões D-G1 a D-G5) e
`docs/specs/portao-stop-sem-codigo-plano.md` (D1: docs só na fase final).
As pipelines de `harness4codex/_contract/pipelines.json` são idênticas às do
harness4claude.

## O defeito

`_handle_stop` (`harness4codex/hook.py:464-484`):

```python
if state.get("status") == "active" and state.get("pipeline") and not state.get("verified"):
    ...bloqueia
```

Não olha fase nem `kind`. Consequências:

1. Nas fases pré-implementação das pipelines de código (`discuss`,
   `brainstorming`, `graph-context`, `write-spec`, `grill-me`, `design-doc`,
   `validate-plan`; `write-spec-light` em L1) cobra evidência de teste que não
   pode existir. Num repositório sem código a única saída verde é fabricar
   pytest.
2. Nas pipelines de docs cobra pytest em qualquer fase. E só
   `evidence_type='test'` liga `verified` (`state_db.py:777`), e `complete` só
   aceita teste fresco (`_has_fresh_test_evidence`, `state_db.py:873-889`):
   uma task de docs não tem como fechar sem teste.

## Censo — função de produção sobre o contrato

`censo_codex.py` (scratchpad da sessão): para cada pipeline do contrato e cada
fase, cria a task por `HarnessStateStore.start_task`, avança por
`HarnessDatabase.transition` / `resolve_gate` reais (com os artefatos que
`ARTIFACT_OBLIGATIONS` exige), sincroniza a projeção com
`cli._sync_task_projection` e chama `hook.handle_payload({"hook_event_name":
"Stop"})`.

Antes do conserto: **52 de 58** pares bloqueiam. Os 6 que não bloqueiam são
`approve-spec` e `approve-plan` de L2-feature, L2-refactor e L2-architecture —
`transition` põe `status='awaiting_gate'` e o `if` exige `active`. Não é regra
de fase, é efeito colateral do status.

| Pipeline | Tipo | Bloqueia hoje |
|---|---|---|
| L1-feature, L1-refactor | test | as 3, incluindo `write-spec-light` |
| L1-bug | test | as 3 |
| L1-review | test | as 2 |
| L1-docs | docs | as 3 |
| L2-feature, L2-architecture | test | 9 de 11 (7 antes de `tdd`) |
| L2-bug | test | as 5 |
| L2-refactor | test | 8 de 10 (6 antes de `tdd`) |
| L2-review | test | as 3 |
| L2-docs | docs | as 4 |

Esperado pela regra da referência: **25 de 58** — o mesmo número do
harness4claude.

## Causa raiz

O portão de Stop do codex não tem regra de fase nenhuma: a condição é só
"pipeline ativa e não verificada". Não existe o equivalente de
`cobra_evidencia_nesta_fase`, nem de `tipo_de_evidencia`. O harness4claude
teve os dois defeitos em sequência (docs em 2026-09-25, fases pré-implementação
em 2026-09-30); o codex nunca recebeu nenhum dos dois consertos.

## Quem lê o que

- `_handle_stop` lê a **projeção** (`state.json`, via `store.load()`):
  `status`, `pipeline`, `verified`, `stop_continuations`. `current_step` e
  `kind` estão na projeção e são sincronizados do banco por
  `_merge_transactional` (store) e `_sync_task_projection` (CLI).
- `stop_continuations` só existe na projeção; o banco não conta continuação.
  Não há `register_stop_continuation` no codex, então o hook é o único
  consumidor da regra.
- Marca d'água (D-G3/D-G4) precisa do banco: a tabela `events` existe
  (`state_db.py`, schema) e `transition`/`resolve_gate` são os únicos
  avanços. `confirm_classification` grava em `transitions`
  (`systematic-debugging -> discuss` numa correção L1-bug → L2-feature), por
  isso a marca não pode ser lida de `transitions`.
- `resolve_gate` não tem chamador no CLI hoje (só a API); entra na marca por
  paridade e porque é o avanço de `approve-plan -> tdd`.

## Controles existentes que codificam o defeito

Cinco testes de `tests/test_hook.py` usam "Implemente exportacao CSV."
(`C2`/feature → `write-spec-light`, fase 1 de 3) e esperam bloqueio:
`test_stop_blocks_unverified_active_pipeline_once`,
`test_stop_keeps_blocking_until_fresh_verification`,
`test_stop_block_output_uses_codex_stop_schema_only`,
`test_stop_escalates_after_two_automatic_continuations_then_allows_human_gate`
e, por escopo, `test_stop_gate_is_scoped_to_session` (espera `""` na outra
sessão — continua valendo). Os quatro primeiros medem o comportamento que este
conserto remove; passam a posicionar a task em `tdd` antes do Stop, que é o
que eles de fato querem medir (bloqueio, schema, escalada).

## Questão aberta para o grill

Docs na fase final: com só `test` ligando `verified`, D1 sozinho ainda cobra
pytest na última fase de docs, e `complete` recusa sem teste. A referência
resolveu isso com `EVIDENCIA_DO_KIND = {"docs": "docs"}` e relatório com hash
(D3). Portar ou não é decisão de escopo.

## Contexto estrutural (fase graph-context)

`graphify update .` no worktree (AST, 2026-09-30, depois de `4ec4047`):
grafo conferido contra `HEAD`. `graphify query` sobre `_handle_stop` devolve
um único chamador, `handle_payload` (`hook.py:522`); os chamados são
`store.load`, `set_pending_gate`, `increment_stop_continuations`, `log_event`,
`_block_stop` e `spool_mirror.drenar_canal`. `transition`, `resolve_gate`,
`confirm_classification` e `reclassify` não se chamam entre si; o CLI chama
`transition` e `confirm_classification`, o store chama `reclassify`
(promoção C0 → C1 em `record_file`).

Consumidores de `verified` / tipo de evidência (grep, conferido com o grafo):
`hook._handle_stop` (`:468`), `state_db.record_evidence` (`:777`),
`state_db.complete` + `_has_fresh_test_evidence` (`:823`, `:873`),
`state.record_verification` (grava sempre `evidence_type="test"`, `:323`) e a
projeção (`state._merge_transactional`, `cli._sync_task_projection`). Nenhum
outro leitor.

## Regra proposta (porta da referência)

Uma função pura em `state_db.py`, `cobra_evidencia_nesta_fase(kind, pipeline,
phase, *, passou_pela_implementacao=False)`, com as mesmas constantes da
referência:

- `FASES_DE_IMPLEMENTACAO = {"tdd", "systematic-debugging"}`.
- Tipo `docs` (`kind == "docs"`, já normalizado por `ContractSnapshot.normalize`):
  cobra só na última fase da pipeline (D1).
- Tipo `test`: cobra da primeira fase de implementação da pipeline em diante;
  em qualquer fase se `passou_pela_implementacao`; em toda fase se a pipeline
  não tem fase de implementação (`review`, D-G2); fase fora da pipeline cobra
  (falha fechada).
- Marca d'água: evento `passou-pela-implementacao` na tabela `events`, gravado
  por `transition` e `resolve_gate` quando o avanço sai de uma fase de
  implementação ou entra nela (D-G3, D-G4). `confirm_classification` e
  `reclassify` não gravam. `task()` passa a renderizar
  `passou_pela_implementacao`.
- `_handle_stop` lê pipeline, fase, `kind` e a marca **do banco**
  (`store.database.task(task_id)`), que é a autoridade; a projeção continua
  dando `status`, `verified` e `stop_continuations`, como hoje. Sem `task_id`
  (projeção legada sem task no banco): comportamento atual, cobra.

`status == active` continua sendo exigido: as fases de gate humano seguem fora
do bloqueio por `awaiting_gate`, como hoje.

## Critérios de aceite (1 AC = 1 teste, `tests/test_portao_pre_implementacao.py`)

- **AC-1 (reprodução).** Task `L2-architecture` em `discuss`, sem evidência:
  Stop não bloqueia, `stop_continuations` fica 0. Falha antes do conserto.
- **AC-2.** Mesma task em `write-spec` e `design-doc`; `L1-feature` em
  `write-spec-light`: Stop não bloqueia.
- **AC-3 (controle).** `L2-architecture` em `tdd` e `verify-multimodel`, sem
  evidência: Stop bloqueia e conta a continuação.
- **AC-4 (controle).** Nas mesmas fases, evidência de teste válida
  (`record_verification`) libera o Stop.
- **AC-5.** `L2-bug` cobra nas 5 fases (D-G1).
- **AC-6.** `L1-review` e `L2-review` cobram em toda fase (D-G2).
- **AC-7.** Task que avançou até `tdd` e foi reclassificada para `L2-feature`
  (volta a `discuss`) continua cobrada (D-G3).
- **AC-8.** Task `L1-bug` corrigida para `L2-feature` por
  `confirm_classification` antes de avançar: `discuss` não cobra (D-G4).
- **AC-9.** `transition` para `tdd`, `transition` saindo de
  `systematic-debugging` e `resolve_gate` de `approve-plan` gravam a marca;
  `confirm_classification` e `reclassify` não.
- **AC-10.** Contrato: todo nome de `FASES_DE_IMPLEMENTACAO` existe em
  `_contract/pipelines.json`; pipeline de tipo `test` sem fase de
  implementação só passa se declarada; censo pela função de produção = 25 de
  58.
- **AC-11.** Fase fora da pipeline cobra.
- **AC-12 (docs, D1).** `L1-docs` e `L2-docs` não bloqueiam antes da última
  fase; bloqueiam nela.

## Grill (2026-09-30)

`wf-grill`, run `wf_e514c266-055`: 5 de 5 lentes vivas, 46 perguntas, 5
bloqueantes. Referência fixada: harness4claude `d3921b7` (conserto) e
`a5789ba` (diagnóstico), ramo `claude/cool-lichterman-5718b9`; D1-D3 de
`docs/specs/portao-stop-sem-codigo-plano.md` em `main` do harness4claude.

Decisões:

- **D-G1 (travada pelo usuário no pedido).** `systematic-debugging` é fase de
  implementação: parte de código existente e fecha num teste de reprodução.
  L2-bug cobra nas 5 fases. [3]
- **D-G2.** `review` (tipo test sem fase de implementação) cobra em toda fase.
  A lista das pipelines assim fica **no teste de contrato**
  (`PIPELINES_TEST_SEM_IMPLEMENTACAO`); o contrato não é editado. [25, 29, 39, 43]
- **D-G3/D-G4 (travadas pelo usuário).** Marca d'água por evento
  `passou-pela-implementacao`, gravado só por `transition` e `resolve_gate`
  **bem-sucedidos** cujo avanço sai de fase de implementação ou entra nela.
  Nunca por `start_task`, `confirm_classification` ou `reclassify`. Uma L1-bug
  corrigida para L2-feature antes de avançar não fica marcada (AC-8); se houve
  código escrito em `systematic-debugging` nessa janela, `complete` ainda exige
  evidência fresca na fase final — mesmo custo declarado da referência. `task()`
  renderiza "existe pelo menos um evento". Reclassificação mantém o `task_id`
  (`UPDATE` nas duas). [7, 8, 13, 14, 15, 16, 27, 40]
- **D3 (decisão do usuário nesta sessão).** Porta também o tipo de evidência
  `docs`: `EVIDENCIA_DO_KIND = {"docs": "docs"}`. Task de `kind` docs só liga
  `verified` com `evidence_type='docs'`, a régua do codex
  (`exit_code = 0`, `tests_collected > 0`, `tests_passed = tests_collected`)
  mais `output_hash IS NOT NULL`. Evidência de outro tipo não mexe em
  `verified` (nem liga, nem desliga). `complete` exige evidência fresca do tipo
  da task. `harness4codex evidence record --type docs` recusa quando
  `--command` não é arquivo existente e grava o sha256 dele. [1, 4, 5, 11]
- **Fonte do tipo.** O `kind` da task **no banco** (normalizado por
  `ContractSnapshot.normalize` na gravação). `kind` nulo ou desconhecido cai em
  `test`. [6, 35, 41]
- **Falha fechada.** `task_id` na projeção e task ausente no banco, erro de
  leitura, `kind` docs com fase nula ou fora da pipeline: cobra. [9, 17, 18, 21, 23, 33]
- **Fontes do Stop.** O gatilho continua o da projeção (`status == active`,
  pipeline não vazia, `verified` falso) — quem já passava hoje, passa. A regra
  de fase lê pipeline, fase, `kind` e marca do banco, que é a autoridade. Se
  elas divergirem, o resultado é, no máximo, o bloqueio de hoje: o conserto só
  **remove** bloqueio quando o banco diz que a fase não é cobrada. [10, 12, 24, 42]
- **Tasks já abertas.** Sem backfill da marca; `stop_continuations` não é
  zerado. Declarado. [19, 34]
- **Censo versionado.** O censo do AC-10 entra como teste em
  `tests/test_portao_pre_implementacao.py`, pela função de produção
  (`handle_payload`). [22, 31]
- **Testes antigos.** Os quatro de `test_hook.py` chegam a `tdd` por
  `transition` real com os artefatos obrigatórios; continuam medindo bloqueio,
  schema e escalada. Nenhum outro controle tem expectativa editada. [28, 30, 36]
- **Deploy/instalação** do hook consertado: fora deste ramo, só com OK do
  usuário depois do merge. [32, 45]

## Boundaries

- ALWAYS: regra única (`cobra_evidencia_nesta_fase`) em `state_db.py`; falha
  fechada em dúvida; suíte inteira verde antes de propor merge.
- NEVER: editar `_contract/`; gravar a marca fora de avanço bem-sucedido;
  liberar Stop por erro de leitura; deploy/instalar sem OK.
- ASK: qualquer controle existente além dos quatro de `test_hook.py` que fique
  vermelho.

## Critérios de aceite adicionais (D3)

- **AC-13.** Task `L1-docs` na fase final: `record_evidence(type='docs')` com
  `output_hash` e régua válida liga `verified`; sem hash, não liga.
- **AC-14.** Task `L1-docs`: evidência `test` válida não liga `verified`;
  evidência `test` vermelha não desliga um `verified` de docs.
- **AC-15.** `complete` numa task de docs aceita evidência `docs` fresca e
  recusa só-teste; numa task de código, o contrário.
- **AC-16.** CLI `evidence record --type docs` sem `--command` ou com caminho
  inexistente sai 2; com arquivo, grava o sha256 dele.
- **AC-17.** O Stop de docs na fase final pede `--type docs` e não fala em
  pytest.

## Falsificação (fase tdd)

- **RED antes do conserto** (`bdd740a`): 24 de 43 reprovados, cada um pelo
  motivo previsto — bloqueio em fase pré-implementação, `passou_pela_implementacao`
  e `cobra_evidencia_nesta_fase` inexistentes, docs sem tipo próprio. Os
  controles AC-3 a AC-7 passavam: o código antigo cobrava tudo.
- **GREEN depois:** 44 de 44 no arquivo novo (AC-11 ganhou o caso "task ausente
  no banco" na curadoria). Os quatro controles de `test_hook.py` reprovaram
  exatamente como previsto no diagnóstico e foram reposicionados em `tdd` por
  `transition` real; nenhum outro teste mudou.
- **Mutantes** (`mutantes_codex.py` no scratchpad; um por vez, restaura sempre,
  aborta se a substituição não casa exatamente uma vez): **16 de 16 mortos**.

| Mutante | Reprovou (amostra) |
|---|---|
| M0 hook ignora a regra (o defeito original) | AC-1, AC-2 ×3, AC-8, AC-10 censo, AC-12 ×2 |
| M1 teste nunca cobra | AC-5, AC-6 ×5, `test_zero_collected_tests_do_not_satisfy_stop_gate` |
| M2 ignora a marca | AC-7 |
| M3 nunca grava a marca | AC-7, AC-9 ×3 |
| M4 pipeline sem implementação nunca cobra | AC-6 ×5, AC-10 censo |
| M5 grava a marca em toda transição | AC-2 ×2, AC-9 ×2, AC-10 censo |
| M6 fase fora da pipeline libera | AC-11 |
| M7 docs cobra em toda fase | AC-12 ×2, AC-10 censo, AC-11 |
| M8 `resolve_gate` não grava a marca | AC-9 (approve-plan) |
| M9 task ilegível libera | AC-11 (task ausente no banco) |
| M10 docs sem hash verifica | AC-13 |
| M11 `record_evidence` só aceita teste | AC-13, AC-14 ×2, AC-15, AC-16 |
| M12 `complete` só aceita teste | AC-15 |
| M13 CLI não ancora no relatório | AC-16 ×2 |
| M14 evidência de outro tipo desverifica | AC-14 |
| M15 mensagem de docs pede teste | AC-17 |

Metade 1 (não bloqueia antes da implementação): M0, M5, M7. Metade 2 (continua
bloqueando depois e libera com evidência válida): M1, M2, M3, M4, M6, M8, M9,
mais os controles AC-3/AC-4 e os quatro de `test_hook.py`.

A skill `codex-harness-workflow` §Evidence and completion passou a dizer onde o
portão cobra e como registrar evidência de docs.
