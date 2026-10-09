"""Guarda de orfao do harness4codex: simbolo publico (funcao, classe, metodo) sem caminho ate uma raiz de producao.

Decisao 7 de master-harness/docs/decisoes-capacidades-orfas.md. O scanner `tools/orfaos.py` e o mesmo arquivo do
master-harness, onde os testes do proprio scanner moram (`master-harness/tests/test_orfaos.py`, arvores sinteticas).
Aqui ficam o guarda sobre este repositorio, a falsificacao nas duas metades e a paridade entre as duas copias.

As raizes deste repositorio vem do host, nao do pyproject: `hooks/hooks.json` executa
`hooks/codex_harness_hook.py`, `scripts/install.sh` e `install.ps1` executam `scripts/install.py`, e os `SKILL.md`
mandam rodar `harness4codex <sub>` (mapeado para `python -m harness4codex` em `varredura.comandos`).
"""

from __future__ import annotations

import dataclasses
import importlib
import importlib.util
import json
import re
import shutil
import subprocess
import sys
from pathlib import Path
from types import MappingProxyType

import pytest

ROOT = Path(__file__).resolve().parent.parent
SCANNER = ROOT / "tools" / "orfaos.py"
FONTE_DO_SCANNER = Path("C:/Users/LHarden2/Documents/projects/master-harness/tools/orfaos.py")


@pytest.fixture(scope="module")
def orf():
    spec = importlib.util.spec_from_file_location("orfaos_hx", SCANNER)
    assert spec and spec.loader
    mod = importlib.util.module_from_spec(spec)
    sys.modules["orfaos_hx"] = mod
    spec.loader.exec_module(mod)
    return mod


class TestRepositorioReal:
    def test_repositorio_real_passa_o_guarda(self, orf):
        p = orf.conferir(ROOT)
        assert p["ready"] is True, orf.mensagem_de_falha(p)

    def test_raizes_vem_dos_arquivos_do_host(self, orf):
        raizes = orf.varrer(ROOT)["raizes"]
        assert {"hooks.codex_harness_hook", "scripts.install", "harness4codex.__main__"} <= set(raizes)

    def test_decisao_6_esta_no_inventario(self, orf):
        linhas = {(d["modulo"], d["nome"]): d for d in orf.ler_inventario(ROOT)["declaracoes"]}
        lease = linhas[("harness4codex.state_db", "HarnessDatabase.acquire_lease")]
        assert lease["categoria"] == "RESERVA_DECLARADA" and "lease" in lease["gatilho"]
        censo = linhas[("harness4codex.agent_workflows", "WorkflowCensus")]
        assert censo["categoria"] == "RESERVA_DECLARADA" and "SubagentStop" in censo["gatilho"]

    def test_copia_derivada_do_escopo_e_julgada_na_fonte(self, orf):
        escopos = orf.ler_inventario(ROOT)["escopos_pendentes"]
        assert [e["prefixo"] for e in escopos] == ["harness4codex/_escopo.py"]
        assert "mh/escopo.py" in escopos[0]["gatilho"]

    def test_scanner_e_o_mesmo_do_master_harness(self):
        """O docstring do scanner afirma que o arquivo e o mesmo nos dois repositorios; isto mede."""
        if not FONTE_DO_SCANNER.is_file():
            pytest.skip("master-harness ausente nesta maquina, ou o scanner ainda nao chegou ao main dele")
        normal = [p.read_bytes().replace(b"\r\n", b"\n") for p in (SCANNER, FONTE_DO_SCANNER)]
        assert normal[0] == normal[1], "tools/orfaos.py derivou da copia do master-harness"


class TestFalsificacao:
    """A prova de que o guarda pega o defeito que existe para pegar, nas duas metades, sobre uma copia do
    repositorio real: intacta passa; com um orfao plantado (funcao de topo, e metodo de classe viva) reprova."""

    @pytest.fixture()
    def copia(self, tmp_path):
        destino = tmp_path / "hx-copia"
        ignorar = shutil.ignore_patterns("__pycache__", ".pytest_tmp_*")
        for pasta in ("harness4codex", "hooks", "scripts", "skills", "tools", "tests", ".github", ".codex-plugin"):
            if (ROOT / pasta).is_dir():
                shutil.copytree(ROOT / pasta, destino / pasta, ignore=ignorar)
        return destino

    def test_copia_intacta_passa(self, orf, copia):
        p = orf.conferir(copia)
        assert p["ready"] is True, orf.mensagem_de_falha(p)

    def test_funcao_plantada_reprova(self, orf, copia):
        alvo = copia / "harness4codex" / "classifier.py"
        alvo.write_text(alvo.read_text(encoding="utf-8") + "\n\ndef plantada_sem_chamador():\n    return 42\n",
                        encoding="utf-8")
        p = orf.conferir(copia)
        assert p["ready"] is False
        assert ("harness4codex.classifier", "plantada_sem_chamador") in {
            (o["modulo"], o["nome"]) for o in p["orfaos_nao_declarados"]}

    def test_metodo_plantado_em_classe_viva_reprova(self, orf, copia):
        alvo = copia / "harness4codex" / "state_db.py"
        texto = alvo.read_text(encoding="utf-8")
        ancora = "    def acquire_lease("
        assert ancora in texto
        plantado = "    def plantado_sem_chamador(self):\n        return 42\n\n"
        alvo.write_text(texto.replace(ancora, plantado + ancora, 1), encoding="utf-8")
        p = orf.conferir(copia)
        assert p["ready"] is False
        assert "HarnessDatabase.plantado_sem_chamador" in {o["nome"] for o in p["orfaos_nao_declarados"]}

    def test_cli_reprova_com_exit_1(self, copia):
        alvo = copia / "harness4codex" / "classifier.py"
        alvo.write_text(alvo.read_text(encoding="utf-8") + "\n\ndef plantada_sem_chamador():\n    return 42\n",
                        encoding="utf-8")
        p = subprocess.run([sys.executable, str(SCANNER), "--raiz", str(copia), "--report"],
                           capture_output=True, text=True, encoding="utf-8", timeout=120, check=False)
        assert p.returncode == 1 and "plantada_sem_chamador" in p.stdout


_SCHEMA_CITADO = re.compile(r"contract/schemas/([\w.-]+\.schema\.json)")
VENDORIZADA = ROOT / "harness4codex" / "_contract"


def _alegacoes_de_schema_falsas(declaracoes, contrato: Path) -> list[str]:
    """Motivo do inventario que cita um schema do contrato tem de apontar para um schema que existe, e, se o simbolo e
    uma dataclass, com o `required` igual aos campos dela. Origem: ate 2026-10-09 o motivo do `NodeResult` dizia
    "validado contra contract/schemas/node-result.schema.json", e nenhum campo batia (L-70 do master-harness)."""
    falhas = []
    for d in declaracoes:
        texto = " ".join(str(d.get(chave, "")) for chave in ("motivo", "gatilho"))
        for nome in _SCHEMA_CITADO.findall(texto):
            schema = contrato / "schemas" / nome
            if not schema.is_file():
                falhas.append(f"{d['modulo']}.{d['nome']}: cita {nome}, ausente de {contrato}")
                continue
            alvo = getattr(importlib.import_module(d["modulo"]), d["nome"].split(".")[0])
            if dataclasses.is_dataclass(alvo):
                campos = {f.name for f in dataclasses.fields(alvo)}
                exigidos = set(json.loads(schema.read_text(encoding="utf-8")).get("required", []))
                if campos != exigidos:
                    falhas.append(f"{d['modulo']}.{d['nome']}: campos {sorted(campos)} != required de {nome} "
                                  f"{sorted(exigidos)}")
    return falhas


#: O motivo do NodeResult ate 2026-10-09, para as duas metades da falsificacao.
MOTIVO_ANTIGO = MappingProxyType({"modulo": "harness4codex.agent_workflows", "nome": "NodeResult",
                                  "motivo": "Resultado de no validado contra "
                                            "contract/schemas/node-result.schema.json."})


class TestMotivoQueCitaSchema:
    """O inventario guarda julgamento; um julgamento que cita o contrato tem de bater com o contrato."""

    def test_inventario_real_nao_alega_schema_falso(self, orf):
        assert _alegacoes_de_schema_falsas(orf.ler_inventario(ROOT)["declaracoes"], VENDORIZADA) == []

    def test_node_result_nao_cita_schema_do_contrato(self, orf):
        """L-70: o formato do NodeResult mora na skill (L-64); o contrato 1.4.0 nao tem schema de no."""
        linhas = [d for d in orf.ler_inventario(ROOT)["declaracoes"] if d["nome"].startswith("NodeResult")]
        assert linhas and not any(_SCHEMA_CITADO.search(d["motivo"]) for d in linhas)
        assert not (VENDORIZADA / "schemas" / "node-result.schema.json").exists()

    # As duas metades: a guarda reprova o motivo antigo sobre a arvore 1.3.0 e o schema ausente, e passa quando o
    # schema citado bate com a dataclass (senao seria a guarda que reprova sempre).

    @staticmethod
    def _contrato_com(tmp_path: Path, required: list[str]) -> Path:
        (tmp_path / "schemas").mkdir()
        (tmp_path / "schemas" / "node-result.schema.json").write_text(json.dumps({"required": required}),
                                                                      encoding="utf-8")
        return tmp_path

    def test_motivo_antigo_sobre_schema_1_3_reprova(self, tmp_path):
        antigo = ["run_id", "role", "status", "findings", "evidence_refs", "coverage", "errors"]
        falhas = _alegacoes_de_schema_falsas([MOTIVO_ANTIGO], self._contrato_com(tmp_path, antigo))
        assert len(falhas) == 1 and "!= required" in falhas[0]

    def test_motivo_com_schema_ausente_reprova(self, tmp_path):
        falhas = _alegacoes_de_schema_falsas([MOTIVO_ANTIGO], tmp_path)
        assert len(falhas) == 1 and "ausente" in falhas[0]

    def test_motivo_com_schema_que_bate_passa(self, tmp_path):
        from harness4codex.agent_workflows import NodeResult

        campos = [f.name for f in dataclasses.fields(NodeResult)]
        assert _alegacoes_de_schema_falsas([MOTIVO_ANTIGO], self._contrato_com(tmp_path, campos)) == []
