from pathlib import Path

from harness4codex import conformance
from harness4codex.conformance import build_capability_report, evidence_is_valid
from harness4codex.contract import ContractSnapshot

ROOT = Path(__file__).resolve().parents[1]


# --- Chaves do CAPABILITY_EVIDENCE contra o contrato (F-048 do censo de fatos do master-harness, 2026-10-11) ---
#
# As chaves do mapa sao ids de capacidade do contrato, escritas de novo aqui. O relatorio
# percorre o contrato (`capability_report`), entao capacidade nova sem linha ja aparece. O
# que ninguem pegava era capacidade que SAIU do contrato e deixou a linha no mapa,
# ignorada em silencio. O contrato vem do mesmo `ContractSnapshot.load` que o relatorio usa.


def chaves_sem_capacidade(mapa: dict) -> list[str]:
    """Chaves do mapa que nao sao id de capacidade do contrato que o adaptador carrega."""
    ids = {item["id"] for item in ContractSnapshot.load().capabilities.get("capabilities", [])}
    return sorted(set(mapa) - ids)


def test_toda_chave_do_capability_evidence_e_capacidade_do_contrato():
    """O portao. Vermelho aqui = evidencia de capacidade que o contrato nao tem mais."""
    sobrando = chaves_sem_capacidade(conformance.CAPABILITY_EVIDENCE)
    assert not sobrando, "chaves do CAPABILITY_EVIDENCE fora do contrato:\n  " + "\n  ".join(sobrando)


def test_chave_velha_no_capability_evidence_e_pega(monkeypatch):
    """Falsificacao: a mesma conta reprova uma capacidade que saiu do contrato."""
    monkeypatch.setitem(conformance.CAPABILITY_EVIDENCE, "capacidade.que-saiu-do-contrato", ["tests/test_cli.py"])
    assert chaves_sem_capacidade(conformance.CAPABILITY_EVIDENCE) == ["capacidade.que-saiu-do-contrato"]


def test_codex_adapter_reports_every_required_contract_capability():
    snapshot = ContractSnapshot.load()
    report = build_capability_report(ROOT)

    assert report["contract_version"] == snapshot.version
    assert report["adapter"] == "harness4codex"
    assert report["snapshot_lock_valid"] is True
    assert set(report["capabilities"]) == set(snapshot.required_capabilities)
    assert all(value["status"] == "native" for value in report["capabilities"].values())
    assert report["conformant"] is True


def test_conformance_evidence_is_resolvable_to_repository_files():
    report = build_capability_report(ROOT)
    for capability in report["capabilities"].values():
        assert capability["evidence"]
        for evidence in capability["evidence"]:
            relative = evidence.split("#", 1)[0]
            assert (ROOT / relative).exists(), evidence


def _repo_com_teste(tmp_path):
    (tmp_path / "tests").mkdir()
    (tmp_path / "tests" / "test_x.py").write_text("def test_existe():\n    pass\n", encoding="utf-8")
    return tmp_path


def test_prova_forte_aceita_arquivo_com_a_ancora_definida(tmp_path):
    root = _repo_com_teste(tmp_path)

    assert evidence_is_valid(root, ["tests/test_x.py#test_existe"]) is True


def test_prova_forte_recusa_ancora_que_o_arquivo_nao_define(tmp_path):
    root = _repo_com_teste(tmp_path)

    assert evidence_is_valid(root, ["tests/test_x.py#test_renomeado"]) is False


def test_prova_forte_recusa_lista_vazia(tmp_path):
    assert evidence_is_valid(_repo_com_teste(tmp_path), []) is False


def test_prova_forte_recusa_diretorio_e_registro_sem_ancora(tmp_path):
    root = _repo_com_teste(tmp_path)

    assert evidence_is_valid(root, ["tests#test_existe"]) is False
    assert evidence_is_valid(root, ["tests/test_x.py"]) is False


def test_relatorio_nao_conta_capacidade_cuja_ancora_sumiu(tmp_path, monkeypatch):
    root = _repo_com_teste(tmp_path)
    monkeypatch.setattr(
        "harness4codex.conformance.CAPABILITY_EVIDENCE",
        {name: ["tests/test_x.py#test_sumiu"] for name in build_capability_report(ROOT)["capabilities"]},
    )

    report = build_capability_report(root)

    assert report["conformant"] is False
