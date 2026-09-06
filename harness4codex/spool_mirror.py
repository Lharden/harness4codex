"""Espelho de coordenacao: uma linha anexada ao spool do master-harness.

## Por que esta peca existe, e por que ela e pequena

O painel de tres arquiteturas do master-harness escolheu spool append-only, e a
frase que decidiu a lente `codex` foi: *"a unica escrita que os dois hosts
executam de forma identica e anexar a um arquivo. Sem lock, sem rede, sem API de
host."*

Este modulo e o lado Codex dessa escrita. Ele e propositalmente **stdlib pura**:
importar o `mh` daqui seria dependencia dura de um pacote que pode nao estar
instalado, e o modo de falha viraria "o hook morre" em vez de "nao ha espelho".

O preco de nao importar e que nada garante, por construcao, que a linha daqui
seja igual a de `mh.spool`. O que garante e um teste no master-harness que
**executa este hook** e compara — nao um teste que releia este arquivo. Copiar o
bloco para dentro do teste mediria a copia.

## O que ele nao faz

Nao le. Nao decide nada. Nao bloqueia. Toda excecao e engolida: um hook que
morre por causa do canal de coordenacao e pior que um hook sem canal, porque o
usuario perde o turno por causa de telemetria.
"""

from __future__ import annotations

import hashlib
import json
import os
import re
import uuid
from datetime import datetime, timezone

__all__ = ["casa", "escopo_de", "espelhar", "ligado", "sessao_de"]

#: Os degraus de `store_mode`, na ordem do ADR-001. O espelho so escreve de
#: `dual_write` em diante — antes disso a escada ainda nao autorizou.
_DEGRAUS = ("shadow", "dual_read", "dual_write", "new_primary", "legacy_ro")


def casa() -> str:
    """A casa do master-harness. `MASTER_HARNESS_HOME` existe para os testes."""
    return os.environ.get("MASTER_HARNESS_HOME") or os.path.join(
        os.path.expanduser("~"), ".master-harness"
    )


def sob_teste_sem_isolamento() -> bool:
    """Roda dentro do pytest sem `MASTER_HARNESS_HOME` proprio?

    Medido em 2026-09-05, poucos minutos depois de o espelho entrar: as suites
    dos dois harness escreveram **44 linhas** no spool de producao, com
    `scope_id: "dir:unknown"` e `session_id: null`. Evento falso num ledger de
    coordenacao e pior que evento ausente — ele parece trabalho de verdade.

    A regra e estreita de proposito. Casa **explicita** continua recebendo,
    porque os testes de integracao do canal precisam escrever em algum lugar; o
    que se recusa e a casa **padrao**, que e o unico caso em que a suite esta
    poluindo sem ter pedido.

    E o mesmo principio do enxerto que os juizes exigiram: um criterio que
    aceita origem de teste blinda em vez de detectar.
    """
    return bool(os.environ.get("PYTEST_CURRENT_TEST")) and not os.environ.get(
        "MASTER_HARNESS_HOME"
    )


def ligado(raiz: str | None = None) -> bool:
    """A escada autorizou a escrita?

    Sem `flags.json` — maquina onde o master-harness nunca passou — devolve
    False. Ausencia nao e autorizacao.
    """
    if sob_teste_sem_isolamento():
        return False
    try:
        with open(os.path.join(raiz or casa(), "flags.json"), encoding="utf-8") as fh:
            degrau = ((json.load(fh) or {}).get("flags") or {}).get("store_mode") or _DEGRAUS[0]
        return _DEGRAUS.index(degrau) >= _DEGRAUS.index("dual_write")
    except (OSError, ValueError, TypeError, AttributeError):
        return False


def _dono_do_worktree(dir_com_git: str) -> str | None:
    """`.git` como arquivo com `gitdir:` aponta o repositorio dono do worktree.

    Submodulo NAO colapsa: ele aponta para `modules/`, e e outro repositorio de
    verdade. Colapsa-lo misturaria dois projetos.
    """
    marcador = os.path.join(dir_com_git, ".git")
    try:
        if not os.path.isfile(marcador):
            return None
        with open(marcador, encoding="utf-8", errors="replace") as fh:
            linha = fh.readline(4096).strip()
    except OSError:
        return None
    if not linha.startswith("gitdir:"):
        return None
    alvo = linha[len("gitdir:") :].strip()
    if not alvo:
        return None
    try:
        if not os.path.isabs(alvo):
            alvo = os.path.join(dir_com_git, alvo)
        alvo = os.path.normpath(alvo)
    except (OSError, ValueError):
        return None
    partes = alvo.replace("\\", "/").rstrip("/").split("/")
    if len(partes) < 3 or partes[-2] != "worktrees":
        return None
    repo = os.path.dirname(os.path.dirname(os.path.dirname(alvo)))
    return repo if os.path.isdir(repo) else None


def escopo_de(cwd: str | None) -> str:
    """`repo:<slug>` ou `dir:<slug>`. A especie fica no proprio valor.

    Sem subprocess, pela mesma razao do harness4claude: isto roda em todo prompt,
    e um `git rev-parse` por prompt custaria mais que a resolucao inteira.
    """
    limpo = (cwd or "").strip().strip("\r\n\t ")
    if not limpo:
        return "dir:unknown"
    try:
        p = os.path.abspath(limpo)
    except (OSError, ValueError):
        return "dir:unknown"
    raiz, especie = None, "dir"
    atual = p
    while True:
        if os.path.exists(os.path.join(atual, ".git")):
            raiz, especie = _dono_do_worktree(atual) or atual, "repo"
            break
        pai = os.path.dirname(atual)
        if pai == atual:
            break
        atual = pai
    alvo = raiz or p
    base = os.path.basename(alvo.rstrip("/\\")) or "root"
    base = re.sub(r"[^A-Za-z0-9._-]+", "-", base).strip("-") or "root"
    digest = hashlib.sha256(os.path.normcase(alvo).encode("utf-8")).hexdigest()[:8]
    return f"{especie}:{base[:40]}-{digest}"


def sessao_de(session_id: str | None) -> str | None:
    """`codex:<legivel>-<hash8>`. None sem sessao.

    O prefixo do host existe porque os dois hosts geram id com formas diferentes
    e ja escreveram no mesmo campo: sem marca, `s-4f2a` e um uuid truncado sao
    indistinguiveis depois.
    """
    limpo = (session_id or "").strip().strip("\r\n\t ")
    if not limpo:
        return None
    legivel = re.sub(r"[^A-Za-z0-9._-]+", "-", limpo).strip("-._") or "session"
    digest = hashlib.sha256(limpo.encode("utf-8")).hexdigest()[:8]
    return f"codex:{legivel[:40]}-{digest}"


def espelhar(
    *,
    cwd: str | None,
    session_id: str | None,
    tipo: str,
    dados: dict,
    epoch: int = 1,
    raiz: str | None = None,
) -> str:
    """Anexa uma linha ao spool. Devolve o `event_id`, ou "" se nada foi escrito.

    **Nunca levanta.** Devolver "" cobre os dois casos — escada desligada e erro
    de escrita — de proposito: quem chama nao tem o que fazer de diferente, e o
    que denuncia o silencio e a ausencia de linhas do Codex no `mh spool ver`.
    """
    try:
        base = raiz or casa()
        if not ligado(base):
            return ""
        sess = sessao_de(session_id)
        registro = {
            "dados": dados,
            "epoch": int(epoch),
            "event_id": uuid.uuid4().hex,
            "host": "codex",
            "scope_id": escopo_de(cwd),
            "session_id": sess,
            "tipo": tipo,
            "ts": datetime.now(timezone.utc).isoformat(),
        }
        # Mesma regra de `mh.spool.caminho_outbox(casa, "codex", <slug nu>)`: o
        # prefixo do host ja esta no nome do arquivo, entao o slug entra nu.
        nu = sess.split(":", 1)[1] if sess else "sem-sessao"
        nome = "".join(c if c.isalnum() or c in "-._" else "-" for c in f"codex-{nu}")[:120]
        alvo = os.path.join(base, "spool", "outbox", nome + ".ndjson")
        os.makedirs(os.path.dirname(alvo), exist_ok=True)
        with open(alvo, "a", encoding="utf-8", newline="\n") as fh:
            fh.write(json.dumps(registro, ensure_ascii=False, sort_keys=True) + "\n")
        return registro["event_id"]
    except (OSError, TypeError, ValueError, AttributeError):
        return ""
