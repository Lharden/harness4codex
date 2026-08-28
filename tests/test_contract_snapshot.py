from harness4codex.contract import ContractSnapshot


def test_vendored_contract_maps_legacy_codex_classification():
    contract = ContractSnapshot.load()

    normalized = contract.normalize("C2", "feature")

    assert normalized == {"tier": "L1", "kind": "feature"}
    assert contract.pipeline("L1", "feature") == [
        "write-spec-light",
        "tdd",
        "verify-against-spec",
    ]


def test_vendored_contract_hash_matches_lock():
    contract = ContractSnapshot.load()

    assert contract.verify_lock() is True
    assert contract.version == "1.0.0"

