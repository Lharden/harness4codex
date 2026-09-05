from pathlib import Path

from harness4codex.conformance import build_capability_report
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
