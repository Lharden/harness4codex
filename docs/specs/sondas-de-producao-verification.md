# Verificacao: lote H2 da troca de sondas (L-61..L-65), harness4codex

**Spec**: master-harness `docs/specs/sondas-de-producao-spec.md` (US-2, US-3, US-5); **design** §2.2, §5.
**Ramo**: `feat/sondas-de-producao` (a partir de `main` 35ae57d). **Medido em**: 2026-10-08.
**Contrato**: 1.3.0 do `main` do master-harness (eb4630d), vendorizado em `harness4codex/_contract/`.

## Commits

| Commit | Conteudo |
|---|---|
| `2b3f68a` | `tests/test_sondas_de_producao.py`: os 10 testes novos, nomes exatos do contrato |
| `b770805` | `CAPABILITY_EVIDENCE` trocado pelas linhas da §2.2 |
| `a9e2112` | copia `contract/` 1.3.0 + pino de `tests/test_contract_snapshot.py` (`1.1.0` → `1.3.0`) |
| `17c82d3` | US-5: linha de comando nas skills `graph-context` e `assimilar` + `test_skills_nomeiam_comando_de_cli_que_o_parser_aceita` |

`tests/test_contract_marcador.py` cita `1.1.0` so em docstring historica (medicao de 2026-10-07); nao fixa versao da
copia e nao foi tocado.

## Sabotagem dos 10 testes novos (AC-2.3)

Cada teste roda duas vezes dentro de uma COPIA temporaria do repositorio (`harness4codex hooks skills tests
.codex-plugin pyproject.toml`, `PYTHONPATH` na copia): intacta (tem de passar) e com o chamador desligado (tem de
reprovar). Os tres instrucionais (L-62, L-64) sao sabotados nas duas metades: o nome que o hook injeta e a frase da
skill. Nada disso entra em commit. Comando:

```
python sabotagem.py <raiz do worktree>      # script no apendice
```

| Teste | Sabotagem (chamador desligado) | Copia intacta | Copia sabotada | Veredito |
|---|---|---|---|---|
| `test_user_prompt_grava_nivel_e_pipeline_do_classificador` | hook.py: `classify_prompt(prompt)` vira `classify_prompt("")` | rc=0 (1 passed in 0.20s) | rc=1 (1 failed in 0.21s) `assert ('L0', 'question') == ('L1', 'bug')` | OK |
| `test_classification_confirm_cli_grava_human_override` | cli.py: `_cmd_classification_confirm` retorna 0 antes de gravar | rc=0 (1 passed in 0.21s) | rc=1 (1 failed in 0.20s) `assert 'human_override' in ''` | OK |
| `test_user_prompt_manda_carregar_workflow_com_fases_sdd` | hook.py: o contexto deixa de nomear `codex-harness-workflow` | rc=0 (1 passed in 0.20s) | rc=1 (1 failed in 0.21s) `assert 'Skill: codex-harness-workflow' in ...` | OK |
| `test_user_prompt_manda_carregar_workflow_com_fases_sdd` | SKILL.md: a cadeia L1 `write-spec-light -> tdd -> ...` some | rc=0 (1 passed in 0.20s) | rc=1 (1 failed in 0.20s) `assert 'write-spec-light -> tdd -> verify-against-spec' in ...` | OK |
| `test_user_prompt_manda_carregar_workflow_com_contrato_de_node_result` | hook.py: o contexto deixa de nomear `codex-harness-workflow` | rc=0 (1 passed in 0.20s) | rc=1 (1 failed in 0.20s) `assert 'Skill: codex-harness-workflow' in ...` | OK |
| `test_user_prompt_manda_carregar_workflow_com_contrato_de_node_result` | SKILL.md: `Reconcile the census with actual returns` some | rc=0 (1 passed in 0.20s) | rc=1 (1 failed in 0.21s) `assert 'Reconcile the census with actual returns' in ...` | OK |
| `test_task_complete_recusa_sem_verificacao_fresca` | cli.py: `_cmd_task_complete` retorna 0 sem chamar `complete` | rc=0 (1 passed in 0.22s) | rc=1 (1 failed in 0.22s) `assert 0 == 2` | OK |
| `test_graph_cli_grava_artefato_de_contexto` | cli.py: `_cmd_graph_context` retorna 0 sem coletar | rc=0 (1 passed in 0.25s) | rc=1 (1 failed in 0.19s) `FileNotFoundError` (o artefato nao foi gravado) | OK |
| `test_user_prompt_de_docs_injeta_pipeline_de_documentacao` | hook.py: `classify_prompt(prompt)` vira `classify_prompt("")` | rc=0 (1 passed in 0.20s) | rc=1 (1 failed in 0.21s) `assert 'question' == 'docs'` | OK |
| `test_arsenal_cli_valida_registro_e_sobreposicao` | cli.py: `_cmd_arsenal_check` retorna 0 sem validar | rc=0 (1 passed in 0.20s) | rc=1 (1 failed in 0.19s) `JSONDecodeError` (a saida do check ficou vazia) | OK |
| `test_hook_por_subprocesso_atende_todo_evento_de_hooks_json` | hooks/codex_harness_hook.py: `raise SystemExit(7)` em vez de `main()` | rc=0 (1 passed in 2.24s) | rc=1 (1 failed in 0.34s) `AssertionError: ('SessionStart', '')` | OK |
| `test_user_prompt_manda_carregar_workflow_com_drop_constrain_retain` | hook.py: o contexto deixa de nomear `codex-harness-workflow` | rc=0 (1 passed in 0.20s) | rc=1 (1 failed in 0.21s) `assert 'Skill: codex-harness-workflow' in ...` | OK |
| `test_user_prompt_manda_carregar_workflow_com_drop_constrain_retain` | SKILL.md: `CONSTRAIN keeps persistent` some | rc=0 (1 passed in 0.20s) | rc=1 (1 failed in 0.20s) `assert 'CONSTRAIN keeps persistent' in ...` | OK |

Resultado: 10 de 10 testes passam intactos e reprovam sabotados (13 sabotagens; 13 de 13 fazem reprovar).

Dois casos reprovam por efeito colateral do chamador desligado, nao por asserção direta sobre o resultado
(`graph`: o arquivo de saida nao existe; `arsenal`: `stdout` vazio nao e JSON). Em ambos o teste conferia o artefato
que o chamador produz, entao o chamador desligado reprova pelo motivo certo.

### US-5 (`test_skills_nomeiam_comando_de_cli_que_o_parser_aceita`)

Falsificacao: em `skills/assimilar/SKILL.md`, `arsenal check --registry` trocado por `arsenal check --registro`
reprova o teste (`SystemExit: 2` do `argparse`); restaurado, passa. A alteracao nao foi commitada.

## Cobranca de entrada (L-65)

`mh.paridade.cobrar_sondas` (design atualizado do master-harness, worktree `jolly-hermann-4f78a5`) contra este
worktree, depois dos quatro commits:

```
SONDAS (L-61, L-65) - mapa x canonico e entrada de producao:
  pendencias declaradas (2) - nao reprovam, tem dono:
    codex integration.harness-lite: dono O4 (P4, P7); causa: previa no hook desligada pela decisao 1; 0 sucessos em 68
    codex integration.science-harness: dono decisao 5 + L-63; causa: a sonda prova o roteamento; o MCP registrado nao e exercitado
  ok: todo mapa bate com o canonico e toda sonda alcanca a entrada declarada
exit 0
```

## Suite e conformidade

- `python -m pytest -p no:cacheprovider -o addopts= -q`: **274 passed** (263 anteriores + 10 sondas + 1 de US-5).
- `python -m harness4codex contract check --json --root .`: `contract_version` 1.3.0, `snapshot_lock_valid: true`,
  `conformant: true`.

## Apendice: script de sabotagem

```python
"""Sabotagem por teste novo, numa COPIA temporaria do repositorio (nunca commitada).

Para cada caso: copia a arvore, desliga o chamador (ou apaga a regra da skill),
roda o teste dentro da copia. Controle: o mesmo teste na copia sem sabotagem
tem de passar (as duas metades).
"""
import os
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

REPO = Path(sys.argv[1]).resolve()
SEL = sys.argv[2:]
PASTAS = ["harness4codex", "hooks", "skills", "tests", ".codex-plugin"]
T = "tests/test_sondas_de_producao.py::"


def substituir(arquivo, antigo, novo):
    def f(root):
        p = root / arquivo
        s = p.read_text(encoding="utf-8")
        assert antigo in s, f"trecho ausente em {arquivo}: {antigo!r}"
        p.write_text(s.replace(antigo, novo, 1), encoding="utf-8", newline="\n")
    return f


def retorna_cedo(arquivo, assinatura, valor="0"):
    return substituir(arquivo, assinatura + "\n", assinatura + f"\n    return {valor}\n")


CLASSIFICA = ("harness4codex/hook.py", "classification = classify_prompt(prompt)", 'classification = classify_prompt("")')
SKILL_NOME = ("harness4codex/hook.py", '"Skill: codex-harness-workflow",', '"Skill: nenhuma",')
SKILL = "skills/codex-harness-workflow/SKILL.md"

CASOS = [
    ("test_user_prompt_grava_nivel_e_pipeline_do_classificador", "...", [substituir(*CLASSIFICA)]),
    ("test_classification_confirm_cli_grava_human_override", "...",
     [retorna_cedo("harness4codex/cli.py", "def _cmd_classification_confirm(args: argparse.Namespace) -> int:")]),
    ("test_user_prompt_manda_carregar_workflow_com_fases_sdd", "...", [substituir(*SKILL_NOME)]),
    ("test_user_prompt_manda_carregar_workflow_com_fases_sdd", "...",
     [substituir(SKILL, "`write-spec-light -> tdd -> verify-against-spec`", "`(sem cadeia)`")]),
    ("test_user_prompt_manda_carregar_workflow_com_contrato_de_node_result", "...", [substituir(*SKILL_NOME)]),
    ("test_user_prompt_manda_carregar_workflow_com_contrato_de_node_result", "...",
     [substituir(SKILL, "Reconcile the census with actual returns", "Check the returns")]),
    ("test_task_complete_recusa_sem_verificacao_fresca", "...",
     [retorna_cedo("harness4codex/cli.py", "def _cmd_task_complete(args: argparse.Namespace) -> int:")]),
    ("test_graph_cli_grava_artefato_de_contexto", "...",
     [retorna_cedo("harness4codex/cli.py", "def _cmd_graph_context(args: argparse.Namespace) -> int:")]),
    ("test_user_prompt_de_docs_injeta_pipeline_de_documentacao", "...", [substituir(*CLASSIFICA)]),
    ("test_arsenal_cli_valida_registro_e_sobreposicao", "...",
     [retorna_cedo("harness4codex/cli.py", "def _cmd_arsenal_check(args: argparse.Namespace) -> int:")]),
    ("test_hook_por_subprocesso_atende_todo_evento_de_hooks_json", "...",
     [substituir("hooks/codex_harness_hook.py", "raise SystemExit(main())", "raise SystemExit(7)")]),
    ("test_user_prompt_manda_carregar_workflow_com_drop_constrain_retain", "...", [substituir(*SKILL_NOME)]),
    ("test_user_prompt_manda_carregar_workflow_com_drop_constrain_retain", "...",
     [substituir(SKILL, "CONSTRAIN keeps persistent", "CONSTRAIN drops persistent")]),
]


def copiar() -> Path:
    base = Path(tempfile.mkdtemp(prefix="sabotagem-"))
    for p in PASTAS:
        shutil.copytree(REPO / p, base / p, ignore=shutil.ignore_patterns("__pycache__", ".pytest_cache"))
    shutil.copy(REPO / "pyproject.toml", base / "pyproject.toml")
    return base


def rodar(root: Path, teste: str):
    env = {**os.environ, "PYTHONPATH": str(root)}
    r = subprocess.run(
        [sys.executable, "-m", "pytest", T + teste, "-q", "-p", "no:cacheprovider", "--no-header", "--tb=line", "-o", "addopts="],
        cwd=root, env=env, capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=600,
    )
    return r.returncode


for teste, _descr, edicoes in CASOS:
    if SEL and not any(s in teste for s in SEL):
        continue
    ctl = copiar()
    c_rc = rodar(ctl, teste)
    shutil.rmtree(ctl, ignore_errors=True)
    sab = copiar()
    for e in edicoes:
        e(sab)
    s_rc = rodar(sab, teste)
    shutil.rmtree(sab, ignore_errors=True)
    print(teste, "controle rc=", c_rc, "sabotada rc=", s_rc, "OK" if c_rc == 0 and s_rc != 0 else "FALHA")
```

(O script da medicao imprime tambem o resumo do pytest e a primeira linha de falha, usadas na tabela; o apendice mostra
o essencial. As descricoes das sabotagens estao na tabela.)
