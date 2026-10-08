"""Sondas do contrato que entram pelo CHAMADOR DE PRODUCAO (L-61, L-65).

Cada teste aqui entra pelo que o Codex chama em uso real: `handle_payload` (o
miolo do hook), `run` (o CLI) ou o `hooks/codex_harness_hook.py` por
subprocesso. O nome do teste e o da posicao declarada em
`contract/behavioral-probes.json` (`adapters` e `entradas`); a entrada aparece
como CHAMADA no corpo do teste ou nos helpers deste arquivo, que e o que a
cobranca do `mh paridade` procura.

Os tres testes instrucionais (L-62, L-64) provam que o hook de
`UserPromptSubmit` manda o modelo carregar `codex-harness-workflow` e que a
skill empacotada traz a regra; a regra em si e texto, e o hook e quem a entrega.

Isolamento: casa temporaria (`HARNESS4CODEX_HOME`, `--home`), sem rede, MCP,
Harness Lite nem modelo; `timeout=60` em todo subprocesso.

Fonte: master-harness `docs/specs/sondas-de-producao-{spec,design,auditoria}.md`.
"""
from __future__ import annotations

import hashlib
import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

from harness4codex.cli import run
from harness4codex.contract import ContractSnapshot
from harness4codex.hook import handle_payload
from harness4codex.state import HarnessStateStore
from harness4codex.state_db import HarnessDatabase

ROOT = Path(__file__).resolve().parents[1]
TIMEOUT = 60

HOOK_SCRIPT = "hooks/codex_harness_hook.py"
HOOKS_JSON = ROOT / "hooks" / "hooks.json"
WORKFLOW_SKILL = ROOT / "skills" / "codex-harness-workflow" / "SKILL.md"

PROMPT_BUG = "Corrija o bug: o login falha com erro ao salvar a sessao do usuario."
PROMPT_FEATURE = "Implemente exportacao CSV."
PROMPT_DOCS = "Confira a API atual do OpenAI na versao 2 antes de configurar."


@pytest.fixture(autouse=True)
def ambiente_isolado(tmp_path, monkeypatch):
    """Casa temporaria e nada de servico externo: sem token do Lite, sem espelho."""
    monkeypatch.setenv("HARNESS4CODEX_HOME", str(tmp_path / "casa"))
    monkeypatch.setenv("MASTER_HARNESS_HOME", str(tmp_path / "mh"))
    monkeypatch.delenv("HARNESS_CONTROL_TOKEN", raising=False)


def _prompt_do_usuario(home: Path, prompt: str) -> str:
    """Roda o hook de UserPromptSubmit pelo `handle_payload` e devolve o contexto injetado."""
    saida = handle_payload({"hook_event_name": "UserPromptSubmit", "prompt": prompt}, harness_home=home)
    return json.loads(saida)["hookSpecificOutput"]["additionalContext"]


def _task_aberta_pelo_hook(home: Path, prompt: str) -> str:
    _prompt_do_usuario(home, prompt)
    return HarnessStateStore(home).load()["task_id"]


def _texto_da_skill() -> str:
    return WORKFLOW_SKILL.read_text(encoding="utf-8")


def test_user_prompt_grava_nivel_e_pipeline_do_classificador(tmp_path):
    home = tmp_path / "casa"
    contexto = _prompt_do_usuario(home, PROMPT_BUG)

    task_id = HarnessStateStore(home).load()["task_id"]
    banco = HarnessDatabase(home)
    task = banco.task(task_id)
    pipeline_do_contrato = ContractSnapshot.load().pipeline("L1", "bug")

    assert (task["tier"], task["kind"]) == ("L1", "bug")
    assert task["pipeline"] == pipeline_do_contrato
    assert banco.classification(task_id)["suggested"] == "L1-bug"
    assert f"Task: {task_id}" in contexto
    assert "Pipeline: " + ", ".join(pipeline_do_contrato) in contexto


def test_classification_confirm_cli_grava_human_override(tmp_path, capsys):
    home = tmp_path / "casa"
    task_id = _task_aberta_pelo_hook(home, PROMPT_FEATURE)
    capsys.readouterr()

    codigo = run(
        [
            "classification", "confirm",
            "--home", str(home),
            "--task", task_id,
            "--tier", "L2",
            "--kind", "architecture",
            "--confidence", "1.0",
            "--source", "human_override",
        ]
    )

    assert codigo == 0
    assert "human_override" in capsys.readouterr().out
    classificacao = HarnessDatabase(home).classification(task_id)
    assert classificacao["source"] == "human_override"
    assert classificacao["final"] == "L2-architecture"
    assert classificacao["agreed"] is False


def test_user_prompt_manda_carregar_workflow_com_fases_sdd(tmp_path):
    contexto = _prompt_do_usuario(tmp_path / "casa", PROMPT_FEATURE)
    skill = _texto_da_skill()

    assert "Skill: codex-harness-workflow" in contexto
    assert "Pipeline: write-spec-light, tdd, verify-against-spec" in contexto
    assert "write-spec-light -> tdd -> verify-against-spec" in skill
    assert (
        "discuss -> brainstorming -> graph-context -> write-spec -> grill-me -> approve-spec"
        " -> design-doc -> validate-plan -> approve-plan -> tdd -> verify-multimodel"
    ) in skill


def test_user_prompt_manda_carregar_workflow_com_contrato_de_node_result(tmp_path):
    contexto = _prompt_do_usuario(tmp_path / "casa", PROMPT_FEATURE)
    skill = _texto_da_skill()

    assert "Skill: codex-harness-workflow" in contexto
    assert "must satisfy `NodeResult`" in skill
    for campo in ("node_id", "status", "summary", "artifacts", "evidence", "risks", "questions"):
        assert f"`{campo}`" in skill
    assert "publish a node census" in skill
    assert "Reconcile the census with actual returns" in skill
    assert "Missing or duplicate nodes are workflow failures" in skill


def test_task_complete_recusa_sem_verificacao_fresca(tmp_path, capsys):
    home = tmp_path / "casa"
    task_id = _task_aberta_pelo_hook(home, PROMPT_FEATURE)
    revisao = HarnessDatabase(home).task(task_id)["revision"]
    capsys.readouterr()

    codigo = run(["task", "complete", "--home", str(home), "--task", task_id, "--expect-revision", str(revisao)])

    assert codigo == 2
    assert "fresh verification evidence" in capsys.readouterr().out
    task = HarnessDatabase(home).task(task_id)
    assert task["status"] != "done"
    assert task["revision"] == revisao


def test_graph_cli_grava_artefato_de_contexto(tmp_path, capsys):
    repo = tmp_path / "repo"
    (repo / "graphify-out").mkdir(parents=True)
    (repo / "modulo.py").write_text("x = 1\n", encoding="utf-8")
    grafo = repo / "graphify-out" / "graph.json"
    grafo.write_text('{"nodes": []}', encoding="utf-8")
    futuro = grafo.stat().st_mtime + 60
    os.utime(grafo, (futuro, futuro))
    saida = tmp_path / "artefatos" / "graph-context.json"

    codigo = run(
        [
            "graph", "context",
            "--repo", str(repo),
            "--task", "t-sonda",
            "--scope", "s-sonda",
            "--query", "quem chama modulo",
            "--output", str(saida),
        ]
    )

    assert codigo == 0
    artefato = json.loads(saida.read_text(encoding="utf-8"))
    assert json.loads(capsys.readouterr().out) == artefato
    assert artefato["task_id"] == "t-sonda"
    assert artefato["scope_id"] == "s-sonda"
    assert artefato["freshness"] == "fresh"
    assert artefato["manifest_hash"] == hashlib.sha256(grafo.read_bytes()).hexdigest()
    assert artefato["queries"][0]["text_hash"] == hashlib.sha256("quem chama modulo".encode("utf-8")).hexdigest()


def test_user_prompt_de_docs_injeta_pipeline_de_documentacao(tmp_path):
    home = tmp_path / "casa"
    contexto = _prompt_do_usuario(home, PROMPT_DOCS)

    task_id = HarnessStateStore(home).load()["task_id"]
    task = HarnessDatabase(home).task(task_id)
    pipeline_do_contrato = ContractSnapshot.load().pipeline("L1", "docs")

    assert task["kind"] == "docs"
    assert task["pipeline"] == pipeline_do_contrato
    assert "Pipeline: " + ", ".join(pipeline_do_contrato) in contexto


def test_arsenal_cli_valida_registro_e_sobreposicao(tmp_path, capsys):
    registro = tmp_path / "arsenal.json"
    registro.write_text(
        json.dumps(
            {
                "schema_version": 1,
                "capabilities": ["knowledge-graph", "semantic-search"],
                "tools": {
                    "graphify": {
                        "status": "adopted",
                        "capabilities": ["knowledge-graph", "semantic-search"],
                        "absorbed_into": None,
                    }
                },
            }
        ),
        encoding="utf-8",
    )
    capsys.readouterr()

    assert run(["arsenal", "check", "--registry", str(registro), "--budget", "2"]) == 0
    assert json.loads(capsys.readouterr().out)["ok"] is True

    assert run(["arsenal", "overlap", "--registry", str(registro), "--capability", "semantic-search"]) == 0
    assert json.loads(capsys.readouterr().out) == ["graphify"]

    assert run(["arsenal", "overlap", "--registry", str(registro), "--capability", "inexistente"]) == 2
    assert "outside vocabulary" in capsys.readouterr().out

    estourado = tmp_path / "estourado.json"
    estourado.write_text(
        json.dumps(
            {
                "schema_version": 1,
                "capabilities": ["knowledge-graph"],
                "tools": {"a": {"status": "adopted", "capabilities": ["fora-do-vocabulario"]}},
            }
        ),
        encoding="utf-8",
    )
    assert run(["arsenal", "check", "--registry", str(estourado)]) == 1
    relatorio = json.loads(capsys.readouterr().out)
    assert relatorio["ok"] is False
    assert any("unknown capabilities" in erro for erro in relatorio["errors"])


def _comandos_registrados() -> dict[str, list[str]]:
    config = json.loads(HOOKS_JSON.read_text(encoding="utf-8"))
    return {
        evento: [h["command"] for grupo in grupos for h in grupo["hooks"]]
        for evento, grupos in config["hooks"].items()
    }


def _hook_por_subprocesso(home: Path, evento: str) -> subprocess.CompletedProcess:
    payload = {"hook_event_name": evento, "prompt": "oi", "session_id": f"sonda-{evento}", "cwd": str(home)}
    return subprocess.run(
        [sys.executable, str(ROOT / HOOK_SCRIPT)],
        input=json.dumps(payload).encode("utf-8"),
        capture_output=True,
        timeout=TIMEOUT,
        env={**os.environ, "HARNESS4CODEX_HOME": str(home)},
        check=False,
    )


def test_hook_por_subprocesso_atende_todo_evento_de_hooks_json(tmp_path):
    home = tmp_path / "casa"
    registrados = _comandos_registrados()
    assert len(registrados) >= 11

    for evento, comandos in registrados.items():
        assert comandos, evento
        assert all(HOOK_SCRIPT in comando for comando in comandos), evento
        resultado = _hook_por_subprocesso(home, evento)
        assert resultado.returncode == 0, (evento, resultado.stderr.decode("utf-8", "replace"))
        assert (home / "heartbeats" / evento).is_file(), evento
        assert b"hook error" not in resultado.stdout, (evento, resultado.stdout)


def test_user_prompt_manda_carregar_workflow_com_drop_constrain_retain(tmp_path):
    contexto = _prompt_do_usuario(tmp_path / "casa", PROMPT_FEATURE)
    skill = _texto_da_skill()

    assert "Skill: codex-harness-workflow" in contexto
    assert "Apply `DROP / CONSTRAIN / RETAIN` once" in skill
    assert "DROP removes a" in skill
    assert "CONSTRAIN keeps persistent" in skill
    assert "RETAIN keeps a" in skill
