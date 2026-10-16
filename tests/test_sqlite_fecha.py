"""Toda conexao SQLite do state_db e fechada ao voltar da operacao.

`with sqlite3.connect(...)` so faz commit/rollback: nao fecha. No Windows o
handle do arquivo fica preso ate o coletor. A prova rastreia cada
`sqlite3.connect` chamado e exige que todas estejam fechadas.
"""

from __future__ import annotations

import sqlite3

import pytest

from harness4codex.state_db import HarnessDatabase


@pytest.fixture
def abertas(monkeypatch):
    original = sqlite3.connect
    lista: list[sqlite3.Connection] = []

    def rastreia(*args, **kwargs):
        con = original(*args, **kwargs)
        lista.append(con)
        return con

    monkeypatch.setattr(sqlite3, "connect", rastreia)
    return lista


def _todas_fechadas(lista):
    assert lista, "a operacao nao abriu conexao nenhuma: o teste nao mede nada"
    seguem = []
    for con in lista:
        try:
            con.execute("SELECT 1")
            seguem.append(con)
        except sqlite3.ProgrammingError:
            pass
    assert seguem == [], f"{len(seguem)} de {len(lista)} conexoes seguem abertas"


def test_state_db_fecha_toda_conexao(tmp_path, abertas):
    db = HarnessDatabase(tmp_path)
    task = db.start_task(scope_id="s", legacy_level="L1", tier="L1", kind="bug",
                         pipeline=["tdd"], prompt="x")
    db.record_evidence(task["task_id"], evidence_type="test", command="pytest", exit_code=0,
                       tests_collected=1, tests_passed=1, output_hash="h")
    _todas_fechadas(abertas)


def test_state_db_connect_fecha_e_faz_commit(tmp_path, abertas):
    db = HarnessDatabase(tmp_path)
    abertas.clear()
    with db._connect() as connection:
        connection.execute("INSERT INTO scopes(scope_id, created_at) VALUES ('c', 'agora')")
    _todas_fechadas(abertas)
    with sqlite3.connect(db.path) as outra:
        assert outra.execute("SELECT COUNT(*) FROM scopes WHERE scope_id = 'c'").fetchone()[0] == 1
    outra.close()
