"""O Stop cobra evidencia so onde ela pode existir.

Diagnostico, decisoes e criterios em
`docs/superpowers/specs/portao-stop-pre-implementacao-diagnostico.md`.

Tudo aqui passa pelas funcoes de producao: a task nasce por
`HarnessStateStore.start_task`, avanca por `HarnessDatabase.transition` e
`resolve_gate`, a projecao e sincronizada como o CLI faz, e o Stop e
`hook.handle_payload`. Nenhum teste escreve fase direto no banco ou na projecao.
"""

import hashlib
import json
import sqlite3
from pathlib import Path

import pytest

from harness4codex import hook
from harness4codex.classifier import Classification
from harness4codex.cli import _sync_task_projection, run
from harness4codex.state import HarnessStateStore
from harness4codex.state_db import ARTIFACT_OBLIGATIONS, HUMAN_GATES, StateTransitionError

CONTRATO = json.loads(
    (Path(hook.__file__).parent / "_contract" / "pipelines.json").read_text(encoding="utf-8")
)["pipelines"]

#: Pipelines de tipo `test` que nao tem fase de implementacao, e por isso cobram
#: em toda fase (D-G2). Declaradas AQUI, nao no contrato: pipeline nova de tipo
#: `test` sem `tdd` nem `systematic-debugging` reprova o AC-10 ate entrar nesta lista.
PIPELINES_TEST_SEM_IMPLEMENTACAO = {"L1-review", "L2-review"}


def _nova_task(home, nome: str) -> tuple[HarnessStateStore, str]:
    tier, kind = nome.split("-", 1)
    store = HarnessStateStore(home)
    store.start_task(Classification(tier, kind, list(CONTRATO[nome]), [], False), "portao")
    return store, store.load()["task_id"]


def _avancar_ate(store: HarnessStateStore, task_id: str, alvo: str) -> dict:
    """Avanca pela pipeline da task ate `alvo`, pelos caminhos de producao."""
    db = store.database
    task = db.task(task_id)
    while task["phase"] != alvo:
        atual = task["phase"]
        if atual in ARTIFACT_OBLIGATIONS:
            task = db.record_artifact(task_id, ARTIFACT_OBLIGATIONS[atual], f"docs/{atual}.md", None)
        if atual in HUMAN_GATES:
            task = db.resolve_gate(task_id, atual, "approve", expected_revision=task["revision"])
        else:
            proxima = task["pipeline"][task["pipeline"].index(atual) + 1]
            task = db.transition(task_id, proxima, expected_revision=task["revision"])
    _sync_task_projection(store.home, task)
    return task


def _stop(home) -> dict | None:
    saida = hook.handle_payload({"hook_event_name": "Stop"}, harness_home=home)
    return json.loads(saida) if saida else None


def _bloqueia(home) -> bool:
    data = _stop(home)
    return bool(data) and data.get("decision") == "block"


def _task_em(home, nome: str, fase: str) -> tuple[HarnessStateStore, str]:
    store, task_id = _nova_task(home, nome)
    _avancar_ate(store, task_id, fase)
    return store, task_id


def _reclassificar(store: HarnessStateStore, task_id: str, nome: str) -> None:
    tier, kind = nome.split("-", 1)
    task = store.database.confirm_classification(
        task_id, tier=tier, kind=kind, pipeline=list(CONTRATO[nome]), source="human_override", confidence=1.0
    )
    _sync_task_projection(store.home, task)


def _pytest_verde(store: HarnessStateStore) -> None:
    store.record_verification(
        "python -m pytest -q", exit_code=0, tests_collected=3, tests_passed=3, output_hash="h"
    )


# --- AC-1 e AC-2: fases antes da implementacao nao cobram -------------------


def test_AC1_architecture_em_discuss_nao_bloqueia_nem_conta(tmp_path):
    store, _ = _task_em(tmp_path, "L2-architecture", "discuss")

    assert _stop(tmp_path) is None
    assert int(store.load().get("stop_continuations") or 0) == 0


@pytest.mark.parametrize(
    ("nome", "fase"),
    [
        ("L2-architecture", "write-spec"),
        ("L2-architecture", "design-doc"),
        ("L1-feature", "write-spec-light"),
    ],
)
def test_AC2_fases_de_planejamento_nao_bloqueiam(tmp_path, nome, fase):
    _task_em(tmp_path, nome, fase)

    assert _stop(tmp_path) is None


# --- AC-3 e AC-4: da implementacao em diante cobra, e a evidencia libera ----


@pytest.mark.parametrize("fase", ["tdd", "verify-multimodel"])
def test_AC3_architecture_da_implementacao_em_diante_bloqueia_e_conta(tmp_path, fase):
    store, _ = _task_em(tmp_path, "L2-architecture", fase)

    assert _bloqueia(tmp_path)
    assert store.load()["stop_continuations"] == 1


@pytest.mark.parametrize("fase", ["tdd", "verify-multimodel"])
def test_AC4_evidencia_de_teste_valida_libera(tmp_path, fase):
    store, _ = _task_em(tmp_path, "L2-architecture", fase)
    _pytest_verde(store)

    assert _stop(tmp_path) is None


# --- AC-5, AC-6, AC-11: onde cobra em toda fase -----------------------------


@pytest.mark.parametrize("fase", CONTRATO["L2-bug"])
def test_AC5_bug_cobra_nas_cinco_fases(tmp_path, fase):
    _task_em(tmp_path, "L2-bug", fase)

    assert _bloqueia(tmp_path)


@pytest.mark.parametrize(
    ("nome", "fase"), [(nome, fase) for nome in sorted(PIPELINES_TEST_SEM_IMPLEMENTACAO) for fase in CONTRATO[nome]]
)
def test_AC6_review_cobra_em_toda_fase(tmp_path, nome, fase):
    _task_em(tmp_path, nome, fase)

    assert _bloqueia(tmp_path)


def test_AC11_fase_fora_da_pipeline_cobra():
    from harness4codex.state_db import cobra_evidencia_nesta_fase

    assert cobra_evidencia_nesta_fase("feature", CONTRATO["L1-feature"], "fase-inexistente")
    assert cobra_evidencia_nesta_fase("feature", CONTRATO["L1-feature"], None)
    assert cobra_evidencia_nesta_fase("docs", CONTRATO["L1-docs"], None) is False


# --- AC-7, AC-8, AC-9: marca d'agua -----------------------------------------


def test_AC7_reclassificada_depois_do_tdd_continua_cobrada(tmp_path):
    store, task_id = _task_em(tmp_path, "L1-bug", "tdd")
    _reclassificar(store, task_id, "L2-feature")

    assert store.database.task(task_id)["phase"] == "discuss"
    assert _bloqueia(tmp_path)


def test_AC8_corrigida_antes_de_avancar_nao_fica_marcada(tmp_path):
    store, task_id = _nova_task(tmp_path, "L1-bug")
    _reclassificar(store, task_id, "L2-feature")

    assert store.database.task(task_id)["phase"] == "discuss"
    assert _stop(tmp_path) is None


def _marcada(store, task_id) -> bool:
    return store.database.task(task_id)["passou_pela_implementacao"] is True


def test_AC9_transition_para_tdd_grava_a_marca(tmp_path):
    store, task_id = _task_em(tmp_path, "L1-feature", "write-spec-light")
    assert _marcada(store, task_id) is False

    _avancar_ate(store, task_id, "tdd")

    assert _marcada(store, task_id)


def test_AC9_transition_saindo_de_systematic_debugging_grava_a_marca(tmp_path):
    store, task_id = _nova_task(tmp_path, "L2-bug")
    assert _marcada(store, task_id) is False

    _avancar_ate(store, task_id, "graph-context")

    assert _marcada(store, task_id)


def test_AC9_resolve_gate_de_approve_plan_grava_a_marca(tmp_path):
    store, task_id = _task_em(tmp_path, "L2-feature", "approve-plan")
    assert _marcada(store, task_id) is False

    task = store.database.task(task_id)
    store.database.resolve_gate(task_id, "approve-plan", "approve", expected_revision=task["revision"])

    assert _marcada(store, task_id)


def test_AC9_resolve_gate_recusado_nao_grava_a_marca(tmp_path):
    store, task_id = _task_em(tmp_path, "L2-feature", "approve-plan")
    task = store.database.task(task_id)

    with pytest.raises(StateTransitionError):
        store.database.resolve_gate(task_id, "approve-plan", "reject", expected_revision=task["revision"])

    assert _marcada(store, task_id) is False


def test_AC9_confirm_classification_e_reclassify_nao_gravam(tmp_path):
    store, task_id = _nova_task(tmp_path, "L1-bug")
    _reclassificar(store, task_id, "L2-feature")
    store.database.reclassify(
        task_id, legacy_level="C1", tier="L1", kind="bug", pipeline=list(CONTRATO["L1-bug"])
    )

    assert _marcada(store, task_id) is False


# --- AC-10: contrato e censo pela funcao de producao ------------------------


def test_AC10_fases_de_implementacao_existem_no_contrato_e_pipelines_sem_elas_estao_declaradas():
    from harness4codex.state_db import FASES_DE_IMPLEMENTACAO, tipo_de_evidencia

    fases_do_contrato = {fase for fases in CONTRATO.values() for fase in fases}
    assert FASES_DE_IMPLEMENTACAO <= fases_do_contrato

    sem_implementacao = {
        nome
        for nome, fases in CONTRATO.items()
        if fases
        and tipo_de_evidencia(nome.split("-", 1)[1]) == "test"
        and not FASES_DE_IMPLEMENTACAO & set(fases)
    }
    assert sem_implementacao == PIPELINES_TEST_SEM_IMPLEMENTACAO


def test_AC10_censo_do_contrato_pelo_stop_de_producao(tmp_path):
    cobrados = []
    total = 0
    for nome, fases in CONTRATO.items():
        for fase in fases:
            home = tmp_path / f"{nome}-{fase}"
            _task_em(home, nome, fase)
            total += 1
            if _bloqueia(home):
                cobrados.append((nome, fase))

    assert total == 58
    assert len(cobrados) == 25, cobrados


# --- AC-12: docs so na fase final (D1) --------------------------------------


@pytest.mark.parametrize("nome", ["L1-docs", "L2-docs"])
def test_AC12_docs_nao_bloqueia_antes_da_fase_final(tmp_path, nome):
    for fase in CONTRATO[nome][:-1]:
        home = tmp_path / fase
        _task_em(home, nome, fase)
        assert _stop(home) is None, fase


@pytest.mark.parametrize("nome", ["L1-docs", "L2-docs"])
def test_AC12_docs_bloqueia_na_fase_final(tmp_path, nome):
    _task_em(tmp_path, nome, CONTRATO[nome][-1])

    assert _bloqueia(tmp_path)


# --- AC-13 a AC-17: evidencia de docs (D3) ----------------------------------


def _evidencia(store, task_id, tipo, *, exit_code=0, collected=4, passed=4, output_hash: str | None = "abc"):
    task = store.database.record_evidence(
        task_id,
        evidence_type=tipo,
        command="docs/specs/x-verification.md" if tipo == "docs" else "python -m pytest -q",
        exit_code=exit_code,
        tests_collected=collected,
        tests_passed=passed,
        output_hash=output_hash,
    )
    _sync_task_projection(store.home, task)
    return task


def test_AC13_evidencia_de_docs_com_hash_liga_verified(tmp_path):
    store, task_id = _task_em(tmp_path, "L1-docs", "verify")

    assert _evidencia(store, task_id, "docs")["verified"] is True
    assert _stop(tmp_path) is None


def test_AC13_evidencia_de_docs_sem_hash_nao_liga(tmp_path):
    store, task_id = _task_em(tmp_path, "L1-docs", "verify")

    assert _evidencia(store, task_id, "docs", output_hash=None)["verified"] is False


def test_AC14_teste_verde_nao_verifica_docs(tmp_path):
    store, task_id = _task_em(tmp_path, "L1-docs", "verify")

    assert _evidencia(store, task_id, "test")["verified"] is False


def test_AC14_teste_vermelho_nao_desverifica_docs(tmp_path):
    store, task_id = _task_em(tmp_path, "L1-docs", "verify")
    _evidencia(store, task_id, "docs")

    assert _evidencia(store, task_id, "test", exit_code=1, passed=2)["verified"] is True


def test_AC14_evidencia_de_docs_nao_verifica_codigo(tmp_path):
    store, task_id = _task_em(tmp_path, "L1-feature", "verify-against-spec")

    assert _evidencia(store, task_id, "docs")["verified"] is False


def test_AC15_complete_de_docs_aceita_evidencia_de_docs(tmp_path):
    store, task_id = _task_em(tmp_path, "L1-docs", "verify")
    task = _evidencia(store, task_id, "docs")

    assert store.database.complete(task_id, expected_revision=task["revision"])["status"] == "done"


def test_AC15_complete_de_docs_recusa_so_teste(tmp_path):
    store, task_id = _task_em(tmp_path, "L1-docs", "verify")
    task = _evidencia(store, task_id, "test")

    with pytest.raises(StateTransitionError):
        store.database.complete(task_id, expected_revision=task["revision"])


def test_AC15_complete_de_codigo_recusa_so_docs(tmp_path):
    store, task_id = _task_em(tmp_path, "L1-feature", "verify-against-spec")
    task = _evidencia(store, task_id, "docs")

    with pytest.raises(StateTransitionError):
        store.database.complete(task_id, expected_revision=task["revision"])


def _cli_evidencia_docs(home, task_id, *extra) -> int:
    return run(
        [
            "evidence", "record", "--home", str(home), "--task", task_id, "--type", "docs",
            "--exit-code", "0", "--tests-collected", "4", "--tests-passed", "4", *extra,
        ]
    )


def test_AC16_cli_recusa_docs_sem_relatorio(tmp_path):
    store, task_id = _task_em(tmp_path, "L1-docs", "verify")

    assert _cli_evidencia_docs(tmp_path, task_id) == 2
    assert _cli_evidencia_docs(tmp_path, task_id, "--command", str(tmp_path / "nao-existe.md")) == 2
    assert store.database.task(task_id)["verified"] is False


def test_AC16_cli_grava_o_sha256_do_relatorio(tmp_path):
    store, task_id = _task_em(tmp_path, "L1-docs", "verify")
    relatorio = tmp_path / "verification.md"
    relatorio.write_text("4 afirmacoes conferidas\n", encoding="utf-8")

    assert _cli_evidencia_docs(tmp_path, task_id, "--command", str(relatorio), "--output-hash", "forjado") == 0

    with sqlite3.connect(store.database.path) as connection:
        gravado = connection.execute(
            "SELECT output_hash FROM evidence WHERE task_id = ? ORDER BY id DESC LIMIT 1", (task_id,)
        ).fetchone()[0]
    assert gravado == hashlib.sha256(relatorio.read_bytes()).hexdigest()
    assert store.database.task(task_id)["verified"] is True


def test_AC17_stop_de_docs_pede_evidencia_de_docs_e_nao_pytest(tmp_path):
    _task_em(tmp_path, "L2-docs", "verify-against-spec")

    data = _stop(tmp_path)

    assert data and data["decision"] == "block"
    assert "--type docs" in data["reason"]
    assert "pytest" not in data["reason"].lower()
