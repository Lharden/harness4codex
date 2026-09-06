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

from . import _escopo

import hashlib
import json
import os
import re
import uuid
from datetime import datetime, timezone

__all__ = [
    "bloco_de_presenca",
    "casa",
    "drenar_canal",
    "escopo_de",
    "espelhar",
    "ligado",
    "marcar_presenca",
    "sessao_de",
]

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


def escopo_de(cwd: str | None) -> str:
    """Delega para a fonte. Ver `_escopo.de_caminho`.

    **Isto passou a honrar `HARNESS_SCOPE=global`, e antes nao honrava.** A
    variavel nao aparecia neste arquivo: com ela ligada, o `mh quem` procurava
    balizas em `global:maquina` enquanto este host as escrevia em `repo:<slug>`,
    e a presenca reportava ninguem em silencio. Nao aparecia porque ninguem liga
    a variavel — e o tipo de defeito que espera.
    """
    return _escopo.de_caminho(cwd).valor


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
        # Sem sessao, o pid do ESCRITOR — nunca um rotulo fixo. `sem-sessao`
        # punha todas as sessoes sem id no mesmo arquivo, e e a exclusividade do
        # arquivo que torna o append sem lock seguro.
        nu = sess.split(":", 1)[1] if sess else f"pid-{os.getpid()}"
        nome = "".join(c if c.isalnum() or c in "-._" else "-" for c in f"codex-{nu}")[:120]
        alvo = os.path.join(base, "spool", "outbox", nome + ".ndjson")
        os.makedirs(os.path.dirname(alvo), exist_ok=True)
        # Retentativa contra a janela do `os.replace` do DRENO. Medido por teste
        # de carga no master-harness: 0,56% a 1,11% dos appends morriam com
        # `PermissionError` quando um dreno rodava em paralelo, e o evento sumia
        # em silencio porque quem chama ignora o retorno.
        import time as _time

        texto = json.dumps(registro, ensure_ascii=False, sort_keys=True) + "\n"
        for espera in (0.0, 0.002, 0.01):
            if espera:
                _time.sleep(espera)
            try:
                with open(alvo, "a", encoding="utf-8", newline="\n") as fh:
                    fh.write(texto)
                return registro["event_id"]
            except OSError:
                continue
        return ""
    except (OSError, TypeError, ValueError, AttributeError):
        return ""


# ---------------------------------------------------------------------------
# Presenca: quem mais trabalha neste escopo agora
# ---------------------------------------------------------------------------
# Aqui o modulo NAO e stdlib pura, e a diferenca e deliberada. O espelho do
# spool escreve uma linha e por isso cabe inteiro em tres funcoes; a presenca
# precisa consultar processo do sistema operacional, e uma quarta copia dessa
# logica seria pior que uma dependencia macia.
#
# Macia: o `mh` e achado pelo marcador `~/.master-harness/mh-root` e importado
# dentro de `try`. Ausente o marcador, ausente a presenca — e nao um hook morto.


def _mh():
    """Importa `mh.presenca` pelo marcador, ou devolve `(None, None)`."""
    try:
        base = casa()
        with open(os.path.join(base, "mh-root"), encoding="utf-8") as fh:
            raiz = fh.readline(4096).strip()
        if not raiz or not os.path.isdir(raiz):
            return (None, None)
        import sys

        if raiz not in sys.path:
            sys.path.insert(0, raiz)
        from mh import presenca as _p

        return (_p, base)
    except Exception:
        return (None, None)


def marcar_presenca(*, cwd: str | None, session_id: str | None) -> bool:
    """Anuncia esta sessao do Codex. Best-effort e silencioso.

    **Hoje sempre devolve False**, e isso e honesto e nao um bug: a baliza tem
    de guardar o pid do PROCESSO DO HOST, e no Codex nao ha equivalente ao
    `CLAUDE_PID`. Descobri-lo exigiria subir a cadeia de ancestrais — medido
    pelo painel em 11,9 ms sobre 410 processos, uma vez por sessao.

    Escrever com `os.getpid()` seria pior que nao escrever: a baliza morreria
    junto com o processo do hook e a leitura a recolheria segundos depois. Foi
    exatamente o que aconteceu do lado do Claude antes da correcao.

    A funcao existe assim, com o motivo escrito, porque o oposto — nao existir —
    esconderia que falta uma decisao. Quando alguem medir a subida de
    ancestrais, e aqui que ela entra.
    """
    if not ligado():
        return False
    _p, base = _mh()
    if _p is None:
        return False
    try:
        pid = _p.pid_do_host("codex")
        if pid is None:
            return False
        return _p.marcar(
            base,
            host="codex",
            session_id=session_id or "",
            escopo=escopo_de(cwd),
            pid=pid,
        )
    except Exception:
        return False


def drenar_canal() -> str:
    """Move o outbox para o ledger. Devolve "" quando correu, ou o aviso.

    Chamado no `Stop`, e nao no `SessionStart`: medido pelo painel nos eventos
    desta maquina, `Stop` disparou **294 vezes** e `SessionEnd` **zero** — e o
    `SessionStart` do Codex nao chama `log_event`, entao apoiar o dreno nele
    seria apoiar em evento nao observado. E o que a decisao D-09 ja dizia: no
    lado Codex, tudo que dependeria de `SessionEnd`/`PreCompact` acontece no
    `Stop`.

    **Silencioso quando corre bem.** A falha, essa, tem de aparecer: enquanto o
    dreno era manual o humano via o traceback, e automatizar sem isso trocaria
    um problema visivel por um invisivel.
    """
    if not ligado():
        return ""
    _p, base = _mh()
    if _p is None:
        return ""
    import sqlite3

    from mh import spool

    con = None
    try:
        os.makedirs(base, exist_ok=True)
        con = sqlite3.connect(os.path.join(base, "ledger.db"), timeout=2.0)
        con.execute("PRAGMA journal_mode = WAL")
        con.execute("PRAGMA busy_timeout = 250")
        rel = spool.drenar(base, con)
    except sqlite3.Error as exc:
        rel = spool.RelatorioDreno(falha=f"{type(exc).__name__}: {exc}")
    except Exception:
        return ""
    finally:
        if con is not None:
            con.close()
    try:
        spool.registrar_dreno(base, rel)
    except Exception:
        pass
    if not rel.correu:
        return (f"CANAL: o dreno de coordenacao FALHOU ({rel.falha}). "
                "O outbox nao foi consumido e nada foi perdido.")
    if rel.cercados or rel.ilegiveis:
        return (f"CANAL: dreno com {len(rel.cercados)} cercado(s) e "
                f"{len(rel.ilegiveis)} ilegivel(is).")
    return ""

def bloco_de_presenca(cwd: str | None) -> str:
    """A linha da vizinhanca, ou "" quando nao ha o que afirmar.

    **So faz afirmacao positiva.** `sozinho` e `nao_verificado` saem vazios, e
    isso nao viola L-09: o hook nunca diz "voce esta sozinho". Quem distingue os
    tres estados e `mh quem`, que sai 0/1/2.
    """
    try:
        if not ligado():
            return ""
        _p, base = _mh()
        if _p is None:
            return ""
        # `pid_proprio` explicito, e o `or -1` carrega a justificativa no lugar
        # onde ela vale: a regra "ninguem se conta" precisa saber quem eu sou, e
        # o Codex ainda nao sabe. Hoje isso e inofensivo porque
        # `marcar_presenca` sempre devolve False — nao existe baliza minha que
        # eu pudesse confundir comigo mesmo. `-1` nao e um pid possivel.
        #
        # Quando alguem medir a subida de ancestrais, `pid_do_host` passa a
        # devolver o pid de verdade e o `or -1` deixa de disparar sozinho. E por
        # isso que ele esta escrito assim, e nao como um `if` que alguem teria de
        # lembrar de remover.
        r = _p.vizinhos(base, escopo_de(cwd), pid_proprio=_p.pid_do_host("codex") or -1,
                        host="codex")
        if r.resposta != _p.ACOMPANHADO:
            return ""
        return "\n\nHARNESS VIZINHANCA: " + r.linha()
    except Exception:
        return ""
