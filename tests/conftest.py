"""conftest.py do harness4codex: a recusa fora do ambiente do repositorio (Onda 3, lote 3-B).

O nucleo e `tests/_ambiente.py`, GERADO: o master-harness e o dono, e a copia daqui sai de
`mh identidade semear --artefato ambiente`. O que e deste repositorio e so a configuracao abaixo: a suite roda em
`<raiz>/.venv` (o `uv.lock` no Python do `.python-version`), sem caminho isento. Fora dele, o `pytest` sai com
`UsageError` nomeando o interpretador usado e o comando certo, e nenhum teste roda.
"""

from __future__ import annotations

import atexit
import os
import shutil
import tempfile
from pathlib import Path

# ANTES de qualquer import do `harness4codex`: importar `harness4codex.hook` carrega o `contract`, que chama
# `_mh_pelo_marcador()` ao carregar. Sem `MASTER_HARNESS_HOME`, o marcador real `~/.master-harness/mh-root` poria o
# master-harness da maquina no `sys.path` ja na coleta, e a suite passaria a depender do estado da maquina (P2).
# Uma casa temporaria vazia tira o marcador real do caminho. Casa explicita vinda do ambiente e respeitada.
if not os.environ.get("MASTER_HARNESS_HOME"):
    _CASA_VAZIA = tempfile.mkdtemp(prefix="h4x-casa-vazia-")
    os.environ["MASTER_HARNESS_HOME"] = _CASA_VAZIA
    atexit.register(shutil.rmtree, _CASA_VAZIA, ignore_errors=True)

import _ambiente  # o diretorio deste conftest ja esta no sys.path (sem __init__.py, modo de importacao padrao)

RAIZ = Path(__file__).resolve().parent.parent


def pytest_configure(config) -> None:
    _ambiente.conferir(config, RAIZ, ".venv")
