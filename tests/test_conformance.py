from pathlib import Path

from harness4codex.conformance import build_capability_report, evidence_is_valid
from harness4codex.contract import ContractSnapshot

ROOT = Path(__file__).resolve().parents[1]


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
