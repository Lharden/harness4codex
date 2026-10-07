"""O `mh` e achado pelo marcador `~/.master-harness/mh-root`, como `spool_mirror._mh()` ja faz para a presenca.

Medido em 2026-10-07: o Python do sistema (`python` puro, que e o que os hooks
deste plugin chamam) tem um `master-harness` editavel apontando para um
worktree apagado. Com ele, `import mh` falha e `arvore_do_contrato()` caia no
vizinho `_contract` 1.1.0, com a flag `contrato = preferido` e a canonica em
1.2.0. A unica diferenca semantica entre as duas e o enum de `status` do
`task-state.schema.json`, que ganhou `superseded`; os pipelines sao iguais.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]

_BLOQUEIO_DO_MH = r'''
import importlib.abc, importlib.machinery, json, sys
FALSO = sys.argv[1]
class _SoOFalso(importlib.abc.MetaPathFinder):
    def find_spec(self, nome, path, target=None):
        if nome != "mh" and not nome.startswith("mh."):
            return None
        spec = importlib.machinery.PathFinder.find_spec(nome, path)
        if spec is not None and str(spec.origin or "").startswith(FALSO):
            return spec
        raise ModuleNotFoundError(f"No module named {nome!r}")
sys.meta_path.insert(0, _SoOFalso())
sys.path.insert(0, sys.argv[2])
from harness4codex import contract
arv, origem = contract.arvore_do_contrato()
print(json.dumps({"arvore": str(arv), "origem": origem}))
'''


@pytest.fixture()
def falso(tmp_path: Path) -> Path:
    """Um `mh` minimo: `contrato.CANONICA` e `flags.get`, o que o contrato usa."""
    raiz = tmp_path / "mh-falso"
    canon = tmp_path / "canonica"
    canon.mkdir()
    (canon / "capabilities.json").write_text("{}", encoding="utf-8")
    pacote = raiz / "mh"
    pacote.mkdir(parents=True)
    (pacote / "__init__.py").write_text("", encoding="utf-8")
    (pacote / "contrato.py").write_text(
        f"from pathlib import Path\nCANONICA = Path({str(canon)!r})\n", encoding="utf-8")
    (pacote / "flags.py").write_text("def get(nome):\n    return 'preferido'\n", encoding="utf-8")
    return raiz


def _rodar(casa: Path, falso: Path) -> dict:
    env = dict(os.environ, MASTER_HARNESS_HOME=str(casa))
    p = subprocess.run([sys.executable, "-c", _BLOQUEIO_DO_MH, str(falso), str(ROOT)],
                       capture_output=True, text=True, timeout=120, env=env)
    assert p.returncode == 0, p.stderr
    return json.loads(p.stdout.strip().splitlines()[-1])


def test_marcador_resolve_com_o_mh_inimportavel(falso: Path, tmp_path: Path) -> None:
    casa = tmp_path / "casa"
    casa.mkdir()
    (casa / "mh-root").write_text(str(falso) + "\n", encoding="utf-8")

    d = _rodar(casa, falso)

    assert d["origem"] == "mh"
    assert Path(d["arvore"]) == tmp_path / "canonica"


def test_sem_marcador_e_sem_mh_cai_no_vizinho(falso: Path, tmp_path: Path) -> None:
    casa = tmp_path / "casa-vazia"
    casa.mkdir()

    d = _rodar(casa, falso)

    assert d["origem"].startswith("vizinho:")
    assert Path(d["arvore"]) == ROOT / "harness4codex" / "_contract"


def test_marcador_para_pasta_inexistente_cai_no_vizinho(falso: Path, tmp_path: Path) -> None:
    casa = tmp_path / "casa"
    casa.mkdir()
    (casa / "mh-root").write_text(str(tmp_path / "apagado") + "\n", encoding="utf-8")

    d = _rodar(casa, falso)

    assert d["origem"].startswith("vizinho:")
