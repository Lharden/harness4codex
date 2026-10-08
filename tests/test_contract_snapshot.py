from pathlib import Path

import harness4codex.contract as _contract
from harness4codex.contract import ContractSnapshot

#: A copia vendorizada, por caminho. `ContractSnapshot.load()` prefere a canonica do master-harness quando o
#: marcador `mh-root` a alcanca (2026-10-07); um teste que se chama "vendored" e le `load()` mediria a arvore que a
#: maquina tem, nao a que o pacote leva.
VENDORIZADA = Path(_contract.__file__).parent / "_contract"


def test_vendored_contract_maps_legacy_codex_classification():
    contract = ContractSnapshot(VENDORIZADA, "vizinho:teste")

    normalized = contract.normalize("C2", "feature")

    assert normalized == {"tier": "L1", "kind": "feature"}
    assert contract.pipeline("L1", "feature") == [
        "write-spec-light",
        "tdd",
        "verify-against-spec",
    ]


def test_vendored_contract_hash_matches_lock():
    contract = ContractSnapshot(VENDORIZADA, "vizinho:teste")

    assert contract.verify_lock() is True
    assert contract.version == "1.3.0"


def test_a_arvore_carregada_tem_lock_valido():
    """Seja qual for a origem (canonica ou vizinho), o que roda bate com o proprio lock."""
    contract = ContractSnapshot.load()

    assert contract.verify_lock() is True
