"""conftest.py do harness4codex: a recusa fora do ambiente do repositorio (Onda 3, lote 3-B).

O nucleo e `tests/_ambiente.py`, GERADO: o master-harness e o dono, e a copia daqui sai de
`mh identidade semear --artefato ambiente`. O que e deste repositorio e so a configuracao abaixo: a suite roda em
`<raiz>/.venv` (o `uv.lock` no Python do `.python-version`), sem caminho isento. Fora dele, o `pytest` sai com
`UsageError` nomeando o interpretador usado e o comando certo, e nenhum teste roda.
"""

from __future__ import annotations

from pathlib import Path

import _ambiente  # o diretorio deste conftest ja esta no sys.path (sem __init__.py, modo de importacao padrao)

RAIZ = Path(__file__).resolve().parent.parent


def pytest_configure(config) -> None:
    _ambiente.conferir(config, RAIZ, ".venv")
