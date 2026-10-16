"""O aviso da sincronia entre as maquinas no SessionStart do Codex (master-harness, US-4: AC-4.14 e AC-4.16).

Paridade com o bloco `MAQUINA_DIGEST` do harness4claude. Este repositorio so le o aviso: o `mh` e achado pelo marcador
`~/.master-harness/mh-root`, e `mh.maquina.avisos.ao_iniciar_sessao` decide o que dizer. Aqui se trava o contrato do
hook: a linha chega ao contexto inicial com a casa, o proprio python e o cwd da sessao; sem `mh` ou sem
`mh.maquina.avisos`, silencio; um `mh.maquina` que levanta vira `MAQUINA: NAO VERIFICADO`; e a suite sem casa propria
nao le a casa real.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

from harness4codex.hook import handle_payload

LINHA = "MAQUINA: fotos de desktop a absorver em fastslr (censo de 12 min): rode `mh maquina chegar`"

AVISA = f'''
import json, pathlib
def ao_iniciar_sessao(casa, *, python, cwd):
    pathlib.Path(casa, "chamado.json").write_text(json.dumps({{"casa": str(casa), "python": python, "cwd": str(cwd)}}))
    return {LINHA!r}
'''


@pytest.fixture
def mh_limpo(monkeypatch: pytest.MonkeyPatch):
    """Cada teste importa o seu `mh` falso: o `sys.modules` e o `sys.path` voltam como estavam."""
    antes = {k: v for k, v in sys.modules.items() if k == "mh" or k.startswith("mh.")}
    for k in antes:
        monkeypatch.delitem(sys.modules, k)
    # Defesa: nenhuma entrada herdada do `sys.path` que tenha um pacote `mh` pode ser achada pelo `find_spec`.
    monkeypatch.setattr(sys, "path", [p for p in sys.path if not (Path(p or ".") / "mh" / "__init__.py").is_file()])
    yield
    for k in [k for k in sys.modules if k == "mh" or k.startswith("mh.")]:
        del sys.modules[k]
    sys.modules.update(antes)


def _casa(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, corpo: str | None, *, maquina: bool = True,
          init_mh: str = "", init_maquina: str = "") -> Path:
    raiz = tmp_path / "mh-falso"
    (raiz / "mh").mkdir(parents=True)
    (raiz / "mh" / "__init__.py").write_text(init_mh, encoding="utf-8")
    if maquina:
        (raiz / "mh" / "maquina").mkdir()
        (raiz / "mh" / "maquina" / "__init__.py").write_text(init_maquina, encoding="utf-8")
        if corpo is not None:
            (raiz / "mh" / "maquina" / "avisos.py").write_text(corpo, encoding="utf-8")
    casa = tmp_path / "casa"
    casa.mkdir()
    (casa / "mh-root").write_text(str(raiz) + "\n", encoding="utf-8")
    monkeypatch.setenv("MASTER_HARNESS_HOME", str(casa))
    return casa


def _inicio(tmp_path: Path) -> str:
    cwd = tmp_path / "repo"
    cwd.mkdir(exist_ok=True)
    return handle_payload({"hook_event_name": "SessionStart", "source": "startup", "cwd": str(cwd)},
                          harness_home=tmp_path / "home")


def _contexto(saida: str) -> str:
    return json.loads(saida)["hookSpecificOutput"]["additionalContext"] if saida else ""


def test_ac_4_14_a_linha_chega_ao_contexto_inicial_do_codex(tmp_path, monkeypatch, mh_limpo) -> None:
    casa = _casa(tmp_path, monkeypatch, AVISA)

    saida = _inicio(tmp_path)

    assert _contexto(saida) == LINHA
    assert json.loads(saida)["hookSpecificOutput"]["hookEventName"] == "SessionStart"
    chamado = json.loads((casa / "chamado.json").read_text(encoding="utf-8"))
    assert Path(chamado["casa"]) == casa and Path(chamado["cwd"]) == tmp_path / "repo"
    assert chamado["python"] == sys.executable


def test_linha_vazia_e_silencio(tmp_path, monkeypatch, mh_limpo) -> None:
    _casa(tmp_path, monkeypatch, "def ao_iniciar_sessao(casa, *, python, cwd):\n    return ''\n")

    assert _inicio(tmp_path) == ""


def test_sem_master_harness_silencio(tmp_path, monkeypatch, mh_limpo) -> None:
    monkeypatch.setenv("MASTER_HARNESS_HOME", str(tmp_path / "casa-vazia"))

    assert _inicio(tmp_path) == ""


@pytest.mark.parametrize("maquina", [True, False])
def test_mh_sem_o_modulo_de_aviso_e_silencio(tmp_path, monkeypatch, mh_limpo, maquina: bool) -> None:
    _casa(tmp_path, monkeypatch, None, maquina=maquina)

    assert _inicio(tmp_path) == ""


def test_modulo_que_levanta_no_import_vira_linha(tmp_path, monkeypatch, mh_limpo) -> None:
    _casa(tmp_path, monkeypatch, "raise RuntimeError('import quebrado')\n")

    assert _contexto(_inicio(tmp_path)) == "MAQUINA: NAO VERIFICADO - RuntimeError: import quebrado"


def test_execucao_que_levanta_vira_linha(tmp_path, monkeypatch, mh_limpo) -> None:
    _casa(tmp_path, monkeypatch, "def ao_iniciar_sessao(casa, *, python, cwd):\n    raise ValueError('censo podre')\n")

    assert _contexto(_inicio(tmp_path)) == "MAQUINA: NAO VERIFICADO - ValueError: censo podre"


def test_suite_sem_casa_propria_nao_le_a_casa_real(tmp_path, monkeypatch, mh_limpo) -> None:
    """Sem `MASTER_HARNESS_HOME`, a casa e a padrao (`~/.master-harness`). Aqui a home e do teste e a casa padrao dela
    aponta para um `mh` que fala: o hook tem de calar mesmo assim, porque a suite nao pediu casa propria."""
    casa = _casa(tmp_path, monkeypatch, AVISA)
    home = tmp_path / "home"
    (home / ".master-harness").mkdir(parents=True)
    (home / ".master-harness" / "mh-root").write_text((casa / "mh-root").read_text(encoding="utf-8"), encoding="utf-8")
    monkeypatch.setenv("HOME", str(home))
    monkeypatch.setenv("USERPROFILE", str(home))
    monkeypatch.delenv("MASTER_HARNESS_HOME")

    assert _inicio(tmp_path) == ""


# AC-4.16: silencio so quando o modulo NAO EXISTE. Os 8 casos medidos no lote 20261016-081709-c78f.
AVISOS_OK = "def ao_iniciar_sessao(casa, *, python, cwd):\n    return 'MAQUINA: ok'\n"
SEM_ENTRADA = "def outra_coisa():\n    return 1\n"
NAO_VERIFICADO = "MAQUINA: NAO VERIFICADO - "


@pytest.mark.parametrize(
    ("nome", "args", "esperado"),
    [
        ("avisos_normal", dict(corpo=AVISOS_OK), "MAQUINA: ok"),
        ("sem_mh_maquina", dict(corpo=None, maquina=False), ""),
        ("runtime_no_init_maquina",
         dict(corpo=AVISOS_OK, init_maquina="raise RuntimeError('init quebrado')\n"),
         NAO_VERIFICADO + "RuntimeError: init quebrado"),
        ("avisos_sem_ao_iniciar_sessao", dict(corpo=SEM_ENTRADA), ""),
        ("submodulo_inexistente_no_init_maquina",
         dict(corpo=AVISOS_OK, init_maquina="from mh.maquina.nao_existe import x\n"),
         NAO_VERIFICADO + "ModuleNotFoundError"),
        ("modulo_externo_no_init_maquina",
         dict(corpo=AVISOS_OK, init_maquina="import modulo_externo_que_falta\n"),
         NAO_VERIFICADO + "ModuleNotFoundError"),
        ("import_quebrado_no_init_mh",
         dict(corpo=AVISOS_OK, init_mh="from mh.nao_existe import y\n"),
         NAO_VERIFICADO + "ModuleNotFoundError"),
        ("attributeerror_no_import_do_avisos",
         dict(corpo="import os\nos.nao_existe\n"),
         NAO_VERIFICADO + "AttributeError"),
    ],
)
def test_os_oito_casos_do_ac_4_16(tmp_path, monkeypatch, mh_limpo, nome: str, args: dict, esperado: str) -> None:
    _casa(tmp_path, monkeypatch, **args)

    contexto = _contexto(_inicio(tmp_path))

    if esperado:
        assert esperado in contexto, f"{nome}: {contexto!r}"
    else:
        assert "MAQUINA" not in contexto, f"{nome}: {contexto!r}"
