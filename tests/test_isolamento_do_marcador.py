"""A suite nao pode depender do `~/.master-harness/mh-root` da maquina (classe P2: ambiente de teste != producao).

Importar `harness4codex.hook` carrega o `contract`, que chama `_mh_pelo_marcador()` ao carregar. Sem `MASTER_HARNESS_HOME`,
o marcador real poe o master-harness real no `sys.path` ja na coleta, e `test_sem_master_harness_silencio` passa a achar o
`mh` pelo caminho herdado. O `tests/conftest.py` fixa uma casa temporaria antes da coleta, e a prova e rodar o teste num
subprocesso sem `MASTER_HARNESS_HOME`, numa HOME falsa cujo marcador aponta para um `mh` que fala.
"""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent

FALA = (
    "def ao_iniciar_sessao(casa, *, python, cwd):\n"
    "    return 'MAQUINA: o mh da maquina falou'\n"
)


def test_a_suite_sem_casa_propria_nao_enxerga_o_marcador_da_maquina(tmp_path: Path) -> None:
    raiz_mh = tmp_path / "mh-que-fala"
    (raiz_mh / "mh" / "maquina").mkdir(parents=True)
    (raiz_mh / "mh" / "__init__.py").write_text("", encoding="utf-8")
    (raiz_mh / "mh" / "maquina" / "__init__.py").write_text("", encoding="utf-8")
    (raiz_mh / "mh" / "maquina" / "avisos.py").write_text(FALA, encoding="utf-8")
    home = tmp_path / "home"
    (home / ".master-harness").mkdir(parents=True)
    (home / ".master-harness" / "mh-root").write_text(str(raiz_mh) + "\n", encoding="utf-8")
    env = {k: v for k, v in os.environ.items()
           if k not in {"MASTER_HARNESS_HOME", "PYTEST_CURRENT_TEST", "PYTHONPATH"}}
    env.update(HOME=str(home), USERPROFILE=str(home), PYTHONUTF8="1")

    r = subprocess.run(
        [sys.executable, "-m", "pytest", "tests/test_maquina_aviso.py::test_sem_master_harness_silencio",
         "-p", "no:xdist", "-p", "no:cacheprovider", "-q"],
        stdin=subprocess.DEVNULL, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
        text=True, encoding="utf-8", errors="replace", check=False, env=env, cwd=str(RAIZ), timeout=300,
    )

    assert r.returncode == 0, r.stdout[-2000:] + r.stderr[-1000:]
