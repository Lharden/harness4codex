"""Guarda de órfão: símbolo público de topo sem caminho até uma raiz de produção.

Decisão 7 de `master-harness/docs/decisoes-capacidades-orfas.md` (2026-10-07): inventário e guarda por
repositório. Porte do `harness4claude/tools/orfaos.py`; a doutrina é a mesma e está no próprio `tools/orfaos.json`:
o scanner mede o fato a cada execução, o inventário guarda o julgamento. **Este arquivo é o mesmo, byte a byte, no
master-harness e no harness4codex**; o que muda entre eles (pastas de código, pastas de host, escopos pendentes)
mora no inventário, em `varredura`.

**Alcançabilidade, não contagem de referência.** Um símbolo citado num teste não roda em produção; um símbolo
chamado só por outro símbolo morto não roda; recursão não é chamador. A pergunta é se existe caminho de uma RAIZ
até ele. Raiz medida: o que o `pyproject.toml` instala (`[project.scripts]`; no `mh`, `mh = "mh.cli:main"`) e o
que os arquivos de host executam (`varredura.host`; no harness4codex, `hooks/hooks.json` e os `SKILL.md`). Raiz
declarada: linha `API_EXTERNA` (o host de outro repositório chama por fora: `from mh import saude` no SessionStart
do harness4claude), `FERRAMENTA_DE_MAO` e `PORTAO_DE_SUITE`; o que elas chamam vive por elas.

O que muda em relação ao porte de origem, porque o código é pacote e não pasta de scripts:

- módulo por nome pontuado: `mh.paridade` e `mh.s1.paridade` são distintos, e por nome de arquivo um salvaria o
  outro;
- classe é símbolo, como função;
- import relativo, reexportação por `__init__`, carga por caminho (`spec_from_file_location(..., "cli_s1.py")`,
  `mh/cli.py:749`) e subprocesso por módulo (`"-m", "mh.estresse"`, `mh/estresse.py:265`) contam como aresta;
- escopo pendente: um prefixo declarado com gatilho (hoje só `mh/s1/`, o kit selado por `sha_kit`,
  `mh/s1/selos.py:179-189`, cujo julgamento espera o fecho do S1, L-36). O órfão de lá aparece no relatório e não
  reprova; o que o kit chama fora dele continua vivo por ele. Tirar o escopo do inventário é o que passa a cobrar
  o kit. Nenhum arquivo do kit é lido para escrita.

**Reporta, nunca corrige**: JSON no stdout, `ready`, exit 1. A exceção é `--sync`, que acrescenta órfão novo com
motivo vazio (o guarda segue vermelho até alguém escrever a frase) e retira linha que ganhou chamador. Nunca apaga
motivo escrito.

Uso:
    python tools/orfaos.py                # JSON, exit 1 se reprovar
    python tools/orfaos.py --report       # legível
    python tools/orfaos.py --sync         # sincroniza tools/orfaos.json
    python tools/orfaos.py --raiz DIR     # outra cópia do repositório
"""

from __future__ import annotations

import argparse
import ast
import json
import re
import sys
from collections import defaultdict, deque
from pathlib import Path

try:
    import tomllib
except ModuleNotFoundError:  # Python 3.10 (harness4codex aceita >=3.10): sem tomllib, sem raiz do pyproject
    tomllib = None

INVENTARIO_REL = Path("tools") / "orfaos.json"

#: O que varrer, quando o inventário não diz (`varredura` no `tools/orfaos.json`). O arquivo `.py` é o mesmo nos
#: repositórios que o usam; o que muda entre eles mora no inventário. `codigo`: pastas cujo `.py` é medido.
#: `host`: pastas cujos arquivos de configuração (`.json`, `.sh`, `.ps1`, `.yml`, `.toml`, e `.md` só se for
#: `SKILL.md`) o host executa ou manda executar: o caminho `x.py`, o `-m pacote` e o `from m import f` citados lá
#: viram raiz. Um caminho sob `tests/` nunca é raiz: seria a prova se autocertificando.
VARREDURA_PADRAO = {"codigo": ["mh"], "host": []}
HOST_EXT = {".sh", ".ps1", ".cmd", ".bat", ".js", ".cjs", ".json", ".yml", ".yaml", ".toml", ".md"}

#: Categorias que são ENTRADA por decisão: o símbolo é raiz declarada e o que ele chama vive por ele. Reserva e
#: órfão não semeiam: o que só eles chamam é parte da reserva ou da dívida, e tem de aparecer.
ENTRADAS = {"API_EXTERNA", "FERRAMENTA_DE_MAO", "PORTAO_DE_SUITE"}

#: O vocabulário do harness4claude mais `PORTAO_DE_SUITE`: função de produção cujo consumidor nomeado é um portão
#: da suíte (um teste que reprova a deriva que ela mede), como `derivados.nao_declarados`. Não é ferramenta de mão
#: (ninguém a roda à mão) nem órfã (alguém a chama, e reprova quando ela acha). O campo `consumidor` aponta o teste,
#: e o guarda confere que o arquivo existe e cita o símbolo: a frase é medida, não só escrita.
CATEGORIAS = {
    "FERRAMENTA_DE_MAO": "decisao",
    "RESERVA_DECLARADA": "decisao",
    "API_EXTERNA": "decisao",
    "PORTAO_DE_SUITE": "decisao",
    "ORFAO": "divida",
}

#: Campo obrigatório por categoria, além de `motivo`.
EXIGE = {"RESERVA_DECLARADA": "gatilho", "API_EXTERNA": "consumidor", "PORTAO_DE_SUITE": "consumidor"}

_CAMINHO_PY = re.compile(r"(?:^|[/\\])(\w+)\.py$")
_PONTUADO = re.compile(r"^\w+(?:\.\w+)+$")


# ------------------------------------------------------------------------------------------------------- coleta ----
def _varredura(raiz: Path) -> dict:
    v = ler_inventario(raiz).get("varredura") or {}
    return {"codigo": list(v.get("codigo") or VARREDURA_PADRAO["codigo"]),
            "host": list(v.get("host") or VARREDURA_PADRAO["host"]),
            # Comando nu citado num arquivo de host -> módulo que ele executa. Ex.: os SKILL.md do harness4codex
            # mandam rodar `harness4codex evidence record ...`, que é `python -m harness4codex`.
            "comandos": dict(v.get("comandos") or {})}


def _modulos(raiz: Path, pastas: list[str]) -> dict[str, Path]:
    out: dict[str, Path] = {}
    for pasta in pastas:
        base = raiz / pasta
        if not base.is_dir():
            continue
        for p in sorted(base.rglob("*.py")):
            if "__pycache__" in p.parts:
                continue
            partes = list(p.relative_to(raiz).with_suffix("").parts)
            if partes[-1] == "__init__":
                partes = partes[:-1]
            out[".".join(partes)] = p
    return out


def _rel(raiz: Path, p: Path) -> str:
    return p.relative_to(raiz).as_posix()


def _base_relativa(mod: str, eh_pacote: bool, no: ast.ImportFrom) -> str:
    base = no.module or ""
    if not no.level:
        return base
    partes = mod.split(".")
    if not eh_pacote:
        partes = partes[:-1]
    if no.level > 1:
        partes = partes[: len(partes) - (no.level - 1)]
    return ".".join(partes + ([base] if base else []))


def _pontuado(n: ast.AST) -> list[str] | None:
    partes: list[str] = []
    while isinstance(n, ast.Attribute):
        partes.append(n.attr)
        n = n.value
    if isinstance(n, ast.Name):
        partes.append(n.id)
        return partes[::-1]
    return None


# ---------------------------------------------------------------------------------------------------- varredura ----
def varrer(raiz: Path, entradas_declaradas: list | None = None) -> dict:
    """Mede: quem existe, quem é raiz, e quem é alcançável a partir dela."""
    raiz = Path(raiz).resolve()
    cfg = _varredura(raiz)
    caminhos = _modulos(raiz, cfg["codigo"])

    arvores: dict[str, ast.Module] = {}
    nao_analisados: list[str] = []
    for mod, p in caminhos.items():
        try:
            arvores[mod] = ast.parse(p.read_text(encoding="utf-8", errors="replace"))
        except SyntaxError:
            nao_analisados.append(_rel(raiz, p))
    mods = set(arvores)
    pacotes = {m for m in mods if caminhos[m].name == "__init__.py"}

    nos: dict[tuple, ast.AST] = {}
    publicos: dict[tuple, dict] = {}
    for mod, tree in arvores.items():
        for n in tree.body:
            if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)) and (mod, n.name) not in nos:
                nos[(mod, n.name)] = n
                if not n.name.startswith("_"):
                    publicos[(mod, n.name)] = {
                        "modulo": mod, "nome": n.name, "arquivo": _rel(raiz, caminhos[mod]), "linha": n.lineno,
                        "tipo": "classe" if isinstance(n, ast.ClassDef) else "funcao"}

    # Método público é símbolo (`StateDB.acquire_lease`, decisão 6, é método). Vive quando a classe vive E o nome
    # do atributo é citado por código vivo (`db.acquire_lease(...)`): por nome, porque o tipo do receptor não é
    # visível sem executar. Conservador: um `.run` qualquer salva todo método `run` de classe viva.
    metodos: dict[tuple, tuple] = {}            # (mod, "C.m") -> (mod, "C")
    metodos_por_nome: dict[str, list] = defaultdict(list)
    for (mod, nome), n in list(nos.items()):
        if not isinstance(n, ast.ClassDef):
            continue
        for f in n.body:
            if isinstance(f, (ast.FunctionDef, ast.AsyncFunctionDef)) and not f.name.startswith("_"):
                k = (mod, f"{nome}.{f.name}")
                if k in nos:
                    continue
                nos[k] = f
                metodos[k] = (mod, nome)
                metodos_por_nome[f.name].append(k)
                if not nome.startswith("_"):
                    publicos[k] = {"modulo": mod, "nome": k[1], "arquivo": _rel(raiz, caminhos[mod]),
                                   "linha": f.lineno, "tipo": "metodo"}

    # alias -> ("mod", modulo) | ("sym", modulo, nome) | ("pkgpath", topo) | ("star", modulo)
    alias: dict[str, dict] = {}
    importa: dict[str, set] = defaultdict(set)
    for mod, tree in arvores.items():
        am: dict = {}
        for n in ast.walk(tree):
            if isinstance(n, ast.ImportFrom):
                base = _base_relativa(mod, mod in pacotes, n)
                for a in n.names:
                    if a.name == "*":
                        if base in mods:
                            am["*" + base] = ("star", base)
                            importa[mod].add(base)
                        continue
                    completo = f"{base}.{a.name}" if base else a.name
                    if completo in mods:
                        am[a.asname or a.name] = ("mod", completo)
                        importa[mod].add(completo)
                    elif base in mods:
                        am[a.asname or a.name] = ("sym", base, a.name)
                        importa[mod].add(base)
            elif isinstance(n, ast.Import):
                for a in n.names:
                    if a.name in mods:
                        importa[mod].add(a.name)
                        am[a.asname or a.name.split(".")[0]] = (
                            ("mod", a.name) if a.asname else ("pkgpath", a.name.split(".")[0]))
            elif isinstance(n, ast.Constant) and isinstance(n.value, str):
                # Carga por caminho e subprocesso por módulo: a única forma de o `mh` chamar `cli_s1.py`,
                # `runner_science.py`, `motor_*.py` e `mh.estresse` em produção.
                for alvo in _modulos_citados(n.value, mod, mods):
                    if alvo != mod:
                        importa[mod].add(alvo)
                        # O módulo carregado vive numa variável sem nome de módulo (`_cli_s1().executar(a)`,
                        # `mh/cli.py:796`): o atributo que não resolve por alias é procurado nele, como num `*`.
                        am["*" + alvo] = ("star", alvo)
        alias[mod] = am

    def canon(base: str, nome: str, prof: int = 0) -> tuple | None:
        if (base, nome) in nos:
            return (base, nome)
        if prof > 5 or f"{base}.{nome}" in mods:
            return None
        a = alias.get(base, {}).get(nome)
        if a and a[0] == "sym":
            return canon(a[1], a[2], prof + 1)
        return None

    def refs(mod: str, node: ast.AST) -> set:
        am = alias.get(mod, {})
        estrelas = [v[1] for v in am.values() if v[0] == "star"]
        out: set = set()

        def por_nome(nome: str):
            for s in estrelas:
                k = canon(s, nome)
                if k:
                    out.add(k)

        for n in ast.walk(node):
            if isinstance(n, ast.Name) and isinstance(n.ctx, ast.Load):
                a = am.get(n.id)
                if a and a[0] == "sym":
                    k = canon(a[1], a[2])
                    if k:
                        out.add(k)
                elif (mod, n.id) in nos:
                    out.add((mod, n.id))
                else:
                    por_nome(n.id)
            elif isinstance(n, ast.Attribute):
                d = _pontuado(n)
                if not d or not (a := am.get(d[0])):
                    por_nome(n.attr)
                    continue
                if a[0] in ("mod", "pkgpath"):
                    atual, i = a[1], 1
                    while i < len(d) and f"{atual}.{d[i]}" in mods:
                        atual, i = f"{atual}.{d[i]}", i + 1
                    if i < len(d):
                        k = canon(atual, d[i])
                        if k:
                            out.add(k)
                elif a[0] == "sym":
                    k = canon(a[1], a[2])
                    if k:
                        out.add(k)
            elif (isinstance(n, ast.Call) and isinstance(n.func, ast.Name) and n.func.id == "getattr"
                    and len(n.args) >= 2 and isinstance(n.args[1], ast.Constant)
                    and isinstance(n.args[1].value, str)):
                alvo = am.get(n.args[0].id) if isinstance(n.args[0], ast.Name) else None
                if alvo and alvo[0] == "mod":
                    k = canon(alvo[1], n.args[1].value)
                    if k:
                        out.add(k)
                else:
                    por_nome(n.args[1].value)
        return out

    def corpo_da_classe(n: ast.ClassDef) -> list:
        """A classe sem os corpos dos métodos públicos, que são nós próprios. Base, decorador, atributo de classe,
        `__init__` e método privado ficam: rodam (ou podem rodar) sempre que a classe vive."""
        return [*n.bases, *n.keywords, *n.decorator_list,
                *(s for s in n.body if not (isinstance(s, (ast.FunctionDef, ast.AsyncFunctionDef))
                                            and not s.name.startswith("_")))]

    def atributos(partes: list) -> set:
        out: set = set()
        for parte in partes:
            for x in ast.walk(parte):
                if isinstance(x, ast.Attribute):
                    out.add(x.attr)
                elif (isinstance(x, ast.Call) and isinstance(x.func, ast.Name) and x.func.id == "getattr"
                        and len(x.args) >= 2 and isinstance(x.args[1], ast.Constant)
                        and isinstance(x.args[1].value, str)):
                    out.add(x.args[1].value)
        return out

    arestas: dict[tuple, set] = {}
    attrs: dict[tuple, set] = {}
    for k, n in nos.items():
        partes = corpo_da_classe(n) if isinstance(n, ast.ClassDef) else [n]
        arestas[k] = set().union(*(refs(k[0], p) for p in partes)) if partes else set()
        attrs[k] = atributos(partes)
    topo: dict[str, set] = {}
    for mod, tree in arvores.items():
        acc: set = set()
        for n in tree.body:
            if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
                continue
            if isinstance(n, ast.Assign) and any(isinstance(t, ast.Name) and t.id == "__all__" for t in n.targets):
                continue    # `__all__` nomeia, não chama
            acc |= refs(mod, n)
        topo[mod] = acc
    topo_attrs = {mod: atributos([n for n in tree.body
                                  if not isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef))])
                  for mod, tree in arvores.items()}
    metodos_da_classe: dict[tuple, list] = defaultdict(list)
    for k, c in metodos.items():
        metodos_da_classe[c].append(k)

    raizes = _raizes(raiz, mods, caminhos, cfg["host"], cfg["comandos"])

    def alcance(sementes_externas: set) -> tuple[set, dict]:
        mod_vivo: dict[str, list[str]] = {m: [orig] for m, (_, orig) in raizes.items()}
        for m, _ in sementes_externas:
            mod_vivo.setdefault(m, ["entrada declarada"])
        fila = deque(mod_vivo)
        while fila:
            m = fila.popleft()
            partes = m.split(".")
            vizinhos = {".".join(partes[:i]) for i in range(1, len(partes))} | importa.get(m, set())
            for alvo in vizinhos:
                if alvo in mods and alvo not in mod_vivo:
                    mod_vivo[alvo] = ["import<-" + m]
                    fila.append(alvo)

        vivos: set = set()
        fila2: deque = deque()
        attrs_vivos: set = set()

        def semear(k):
            if k in nos and k not in vivos:
                vivos.add(k)
                fila2.append(k)
                citar(attrs.get(k, ()))
                for metodo in metodos_da_classe.get(k, ()):      # a classe nasceu: métodos já citados vivem
                    if metodo[1].split(".", 1)[1] in attrs_vivos:
                        semear(metodo)

        def citar(nomes):
            for nome in set(nomes) - attrs_vivos:
                attrs_vivos.add(nome)
                for metodo in metodos_por_nome.get(nome, ()):
                    if metodos[metodo] in vivos:
                        semear(metodo)

        for m in mod_vivo:
            citar(topo_attrs.get(m, ()))

        for m, (simbolos, _) in raizes.items():
            for s in simbolos:
                k = canon(m, s)
                if k:
                    semear(k)
        for k in sementes_externas:
            semear(k)
        for m in mod_vivo:
            for k in topo.get(m, ()):
                semear(k)
            for v in alias.get(m, {}).values():
                if v[0] == "sym":
                    k = canon(v[1], v[2])
                    if k:
                        semear(k)
        while fila2:
            k = fila2.popleft()
            for alvo in arestas.get(k, ()):
                if alvo != k:      # recursão não é chamador
                    semear(alvo)
        return vivos, mod_vivo

    # Duas medidas: só com as raízes medidas, e com as entradas declaradas do inventário (ENTRADAS) como raízes. A
    # primeira decide se a linha de entrada ficou obsoleta: só quando o próprio repositório passou a chamar o
    # símbolo — medir com a linha que o mantém vivo se autoconfirmaria.
    if entradas_declaradas is None:
        entradas_declaradas = [(d.get("modulo"), d.get("nome")) for d in ler_inventario(raiz)["declaracoes"]
                               if d.get("categoria") in ENTRADAS]
    vivos_internos, _ = alcance(set())
    vivos, mod_vivo = alcance({k for k in entradas_declaradas if k in nos})

    vereditos = {}
    for k, info in publicos.items():
        if k in vivos:
            vereditos[k] = "viva"
        elif info["modulo"] not in mod_vivo:
            vereditos[k] = "modulo_morto"
        else:
            vereditos[k] = "inalcancavel"

    return {"publicos": publicos, "vereditos": vereditos,
            "vivos_internos": {k for k in publicos if k in vivos_internos},
            "raizes": {m: orig for m, (_, orig) in raizes.items()},
            "modulos_vivos": sorted(mod_vivo), "nao_analisados": nao_analisados}


def _modulos_citados(texto: str, mod: str, mods: set) -> set:
    """Módulos que uma constante de texto nomeia por caminho (`x/cli_s1.py`) ou por nome pontuado (`mh.estresse`).

    Caminho é resolvido pelo nome do arquivo; havendo homônimos (`paridade.py` mora em `mh` e em `mh/s1`), vale o
    que está sob o pacote de quem cita, e só na falta dele todos os homônimos — conservador: pode salvar um órfão,
    nunca inventar um.
    """
    if _PONTUADO.match(texto) and texto in mods:
        return {texto}
    m = _CAMINHO_PY.search(texto)
    if not m:
        return set()
    stem = m.group(1)
    candidatos = {x for x in mods if x.split(".")[-1] == stem}
    pacote = mod.rsplit(".", 1)[0]
    perto = {x for x in candidatos if x.startswith(pacote + ".")}
    return perto or candidatos


def _raizes(raiz: Path, mods: set, caminhos: dict[str, Path], pastas_host: list[str],
            comandos: dict[str, str] | None = None) -> dict[str, tuple[set, str]]:
    """Módulo raiz -> (símbolos chamados por fora, origem). Duas fontes:

    - `[project.scripts]` do `pyproject.toml`: o que o pacote instalado expõe;
    - arquivos de configuração das pastas de host (`varredura.host`): caminho `x.py` (inclusive relativo à pasta do
      próprio arquivo, como `"$SCRIPT_DIR/install.py"`), `-m pacote`, `from m import f` e comando nu mapeado em
      `varredura.comandos`, citados onde o host executa.
    """
    comandos = {c: m for c, m in (comandos or {}).items() if m in mods}
    pat_cmd = (re.compile(r"(?:^|[\s`\"'(])(" + "|".join(re.escape(c) for c in comandos) + r")\s+[a-z]",
                          re.MULTILINE) if comandos else None)
    out: dict[str, tuple[set, str]] = {}

    def anotar(mod: str, simbolos: set, origem: str):
        atual = out.get(mod)
        out[mod] = ((atual[0] if atual else set()) | simbolos, atual[1] if atual else origem)

    p = raiz / "pyproject.toml"
    if p.is_file() and tomllib is not None:
        try:
            dados = tomllib.loads(p.read_text(encoding="utf-8"))
        except tomllib.TOMLDecodeError:
            dados = {}
        for grupo in ("scripts", "gui-scripts"):
            for nome, alvo in (dados.get("project", {}).get(grupo, {}) or {}).items():
                modulo, _, simbolo = str(alvo).partition(":")
                if modulo in mods:
                    anotar(modulo, {simbolo.split(".")[0]} if simbolo else set(),
                           f"pyproject.toml [project.{grupo}] {nome}")

    if not pastas_host:
        return out
    por_caminho = {_rel(raiz, c): m for m, c in caminhos.items() if m in mods}
    nomes = "|".join(re.escape(m) for m in sorted(mods, key=len, reverse=True))
    pat_m = re.compile(r"(?:^|[\s\"'`(])-m\s+(" + nomes + r")\b")
    pat_from = re.compile(r"\bfrom\s+(" + nomes + r")\s+import\s+([\w, ]+)")
    pat_import = re.compile(r"^\s*import\s+(" + nomes + r")\b", re.MULTILINE)
    pat_py = re.compile(r"[\w./\\${}-]*?\w+\.py\b")
    for pasta in pastas_host:
        base = raiz / pasta
        if not base.is_dir():
            continue
        for arq in sorted(base.rglob("*")):
            rel = _rel(raiz, arq)
            if (not arq.is_file() or arq.suffix not in HOST_EXT or "__pycache__" in arq.parts
                    or rel == INVENTARIO_REL.as_posix()
                    or (arq.suffix == ".md" and arq.name != "SKILL.md")):
                continue
            texto = arq.read_text(encoding="utf-8", errors="replace")
            for m in pat_py.finditer(texto):
                citado = m.group(0).replace("\\", "/")
                if citado.startswith("tests/") or "/tests/" in citado:
                    continue
                alvo = next((mod for c, mod in por_caminho.items()
                             if citado == c or citado.endswith("/" + c)), None)
                if alvo is None:
                    # Relativo à pasta do próprio arquivo: `"$SCRIPT_DIR/install.py"`, `Join-Path $PSScriptRoot
                    # 'install.py'`. Só quando o citado não traz pasta própria ou começa por variável.
                    nome = citado.rsplit("/", 1)[-1]
                    if "/" not in citado or citado.startswith("$"):
                        alvo = por_caminho.get(_rel(raiz, arq.parent / nome))
                if alvo:
                    anotar(alvo, set(), rel)
            if pat_cmd:
                for m in pat_cmd.finditer(texto):
                    anotar(comandos[m.group(1)], set(), rel)
            for m in pat_m.finditer(texto):
                alvo = m.group(1)
                anotar(alvo, set(), rel)
                if f"{alvo}.__main__" in mods:
                    anotar(f"{alvo}.__main__", set(), rel)
            for m in pat_from.finditer(texto):
                anotar(m.group(1), {s.strip().split(" as ")[0].strip() for s in m.group(2).split(",") if s.strip()},
                       rel)
            for m in pat_import.finditer(texto):
                anotar(m.group(1), set(), rel)
    return out


# --------------------------------------------------------------------------------------------------- inventário ----
def ler_inventario(raiz: Path) -> dict:
    p = Path(raiz) / INVENTARIO_REL
    if not p.is_file():
        return {"versao": 1, "declaracoes": [], "escopos_pendentes": []}
    try:
        dados = json.loads(p.read_text(encoding="utf-8"))
    except json.JSONDecodeError as erro:
        raise SystemExit(f"{INVENTARIO_REL.as_posix()} nao e JSON valido: {erro}") from erro
    dados.setdefault("declaracoes", [])
    dados.setdefault("escopos_pendentes", [])
    return dados


def _informa(texto: str, nome: str) -> bool:
    """Motivo que só repete o nome não informa: sem isto o inventário vira `# noqa` em massa."""
    limpo = re.sub(r"[^\w\s]", " ", (texto or "")).lower().split()
    return bool(limpo) and set(limpo) - {nome.lower()} != set()


def _teste_cita(raiz: Path, consumidor: str, nome: str) -> bool:
    """`tests/x.py::Classe::teste` existe sob `tests/` e o arquivo cita o símbolo pelo nome."""
    arquivo = consumidor.split("::", 1)[0].strip()
    p = Path(raiz) / arquivo
    if not arquivo.startswith("tests/") or not p.is_file():
        return False
    texto = p.read_text(encoding="utf-8", errors="replace")
    nome = nome.rsplit(".", 1)[-1]      # método: o teste cita `a.completa`, não `Arvore.completa`
    return re.search(rf"\b{re.escape(nome)}\b", texto) is not None and all(
        re.search(rf"\b(?:class|def)\s+{re.escape(parte)}\b", texto) for parte in consumidor.split("::")[1:])


def _ganhou_chamador(d: dict, k: tuple, m: dict) -> bool:
    """A linha deixou de valer. Para entrada declarada (ENTRADAS), só quando o próprio repositório passou a chamar:
    a linha é a raiz que a mantém viva, e medir com ela se autoconfirmaria."""
    if d.get("categoria") in ENTRADAS:
        return k in m["vivos_internos"]
    return m["vereditos"].get(k) == "viva"


def _pendente(arquivo: str, escopos: list[dict]) -> dict | None:
    return next((e for e in escopos if arquivo.startswith(e.get("prefixo") or "\0")), None)


def conferir(raiz: Path, medida: dict | None = None) -> dict:
    """Confronta o medido com o declarado."""
    raiz = Path(raiz).resolve()
    m = medida or varrer(raiz)
    inv = ler_inventario(raiz)
    escopos = inv["escopos_pendentes"]

    escopos_invalidos = [
        {"prefixo": e.get("prefixo", ""), "por_que": por_que}
        for e in escopos
        for por_que in (["sem_prefixo"] if not (e.get("prefixo") or "").strip() else [])
        + (["sem_gatilho"] if not (e.get("gatilho") or "").strip() else [])
        + (["motivo_vazio"] if not (e.get("motivo") or "").strip() else [])
    ]

    declarado: dict[tuple, dict] = {}
    invalidas: list[dict] = []
    for d in inv["declaracoes"]:
        k = (d.get("modulo"), d.get("nome"))
        declarado[k] = d
        base = {"modulo": k[0], "nome": k[1], "arquivo": d.get("arquivo", "")}
        if d.get("categoria") not in CATEGORIAS:
            invalidas.append({**base, "por_que": "categoria_invalida"})
        elif not (d.get("motivo") or "").strip():
            invalidas.append({**base, "por_que": "motivo_vazio"})
        elif not _informa(d["motivo"], k[1] or ""):
            invalidas.append({**base, "por_que": "motivo_nao_informa"})
        elif d["categoria"] in EXIGE and not (d.get(EXIGE[d["categoria"]]) or "").strip():
            invalidas.append({**base, "por_que": f"sem_{EXIGE[d['categoria']]}"})
        elif d["categoria"] == "PORTAO_DE_SUITE" and not _teste_cita(raiz, d["consumidor"], k[1] or ""):
            invalidas.append({**base, "por_que": "consumidor_nao_cita"})

    orfaos, pendentes = [], []
    for k, info in sorted(m["publicos"].items()):
        if m["vereditos"][k] == "viva" or k in declarado:
            continue
        item = {**info, "veredito": m["vereditos"][k]}
        (pendentes if _pendente(info["arquivo"], escopos) else orfaos).append(item)

    obsoletas = []
    for k, d in sorted(declarado.items(), key=lambda x: (str(x[0][0]), str(x[0][1]))):
        base = {"modulo": k[0], "nome": k[1], "arquivo": d.get("arquivo", ""), "motivo": d.get("motivo", "")}
        if _ganhou_chamador(d, k, m):
            obsoletas.append({**base, "por_que": "ganhou_chamador"})
        elif k not in m["publicos"]:
            obsoletas.append({**base, "por_que": "alvo_sumiu"})

    por_categoria: dict[str, int] = defaultdict(int)
    for d in inv["declaracoes"]:
        por_categoria[d.get("categoria", "?")] += 1

    ready = (not (orfaos or obsoletas or invalidas or escopos_invalidos or m["nao_analisados"])
             and bool(m["raizes"]))
    return {
        "ready": ready,
        "total": len(m["publicos"]),
        "vivas": sum(1 for v in m["vereditos"].values() if v == "viva"),
        "raizes": len(m["raizes"]),
        "declaradas": len(inv["declaracoes"]),
        "por_categoria": dict(por_categoria),
        "orfaos_nao_declarados": orfaos,
        "declaracoes_obsoletas": obsoletas,
        "declaracoes_invalidas": invalidas,
        "escopos_invalidos": escopos_invalidos,
        "pendentes": pendentes,
        "escopos_pendentes": [{"prefixo": e.get("prefixo"), "gatilho": e.get("gatilho")} for e in escopos],
        "arquivos_nao_analisados": m["nao_analisados"],
        "comando": "python tools/orfaos.py --sync",
    }


def sincronizar(raiz: Path) -> dict:
    """Acrescenta órfão novo (motivo vazio: sincronizar não é aprovar) e retira linha que ganhou chamador.

    Nunca apaga motivo escrito: alvo que sumiu vira `obsoleta: true` e fica, para recolagem à mão. Símbolo de
    escopo pendente não entra: o julgamento dele espera o gatilho do escopo.
    """
    raiz = Path(raiz).resolve()
    m = varrer(raiz)
    inv = ler_inventario(raiz)
    p = raiz / INVENTARIO_REL
    p.parent.mkdir(parents=True, exist_ok=True)

    saiu: list[str] = []
    mantidas: list[dict] = []
    for d in inv["declaracoes"]:
        k = (d.get("modulo"), d.get("nome"))
        if _ganhou_chamador(d, k, m):
            saiu.append(f"{k[0]}.{k[1]}")
            continue
        if k not in m["publicos"]:
            d = {**d, "obsoleta": True}
        else:
            d.pop("obsoleta", None)
        mantidas.append(d)

    conhecidas = {(d.get("modulo"), d.get("nome")) for d in mantidas}
    novas = []
    for k, info in sorted(m["publicos"].items()):
        if (m["vereditos"][k] == "viva" or k in conhecidas
                or _pendente(info["arquivo"], inv["escopos_pendentes"])):
            continue
        novas.append({"modulo": k[0], "nome": k[1], "arquivo": info["arquivo"], "categoria": "ORFAO", "motivo": ""})

    inv["declaracoes"] = sorted(mantidas + novas, key=lambda d: (d.get("arquivo", ""), d.get("nome", "")))
    p.write_text(json.dumps(inv, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    return {"removidas": saiu, "acrescentadas": [f"{d['modulo']}.{d['nome']}" for d in novas],
            "total": len(inv["declaracoes"])}


# -------------------------------------------------------------------------------------------------------- saída ----
def mensagem_de_falha(payload: dict) -> str:
    """Diz qual caso é, e só promete verde no que o comando resolve sozinho."""
    if payload["ready"]:
        return ""
    linhas: list[str] = []
    if not payload["raizes"]:
        linhas.append("NENHUMA RAIZ encontrada (pyproject.toml [project.scripts] nem arquivo de host em "
                      "varredura.host). Zero raiz e scanner cego, nao 'nada roda aqui': reprovado de proposito.")
    for a in payload["arquivos_nao_analisados"]:
        linhas.append(f"NAO PARSEIA  {a}  (os simbolos dele sumiram da conta)")
    for o in payload["orfaos_nao_declarados"]:
        linhas.append(f"ORFAO NAO DECLARADO  {o['arquivo']}:{o['linha']}  {o['modulo']}.{o['nome']}  [{o['veredito']}]")
    for d in payload["declaracoes_obsoletas"]:
        porque = ("ganhou chamador de producao: a linha nao vale mais" if d["por_que"] == "ganhou_chamador"
                  else "o alvo sumiu do codigo (rename? delecao?)")
        linhas.append(f"LINHA OBSOLETA  {d['modulo']}.{d['nome']}  {porque}")
    for d in payload["declaracoes_invalidas"]:
        porque = {"categoria_invalida": "categoria fora do vocabulario: " + ", ".join(sorted(CATEGORIAS)),
                  "motivo_vazio": "motivo vazio",
                  "motivo_nao_informa": "o motivo so repete o nome",
                  "sem_gatilho": "RESERVA_DECLARADA sem `gatilho` (o que a arma)",
                  "sem_consumidor": "sem `consumidor` (quem chama: arquivo do host, ou tests/x.py::Classe)",
                  "consumidor_nao_cita": "o `consumidor` nao existe sob tests/ ou nao cita o simbolo",
                  }[d["por_que"]]
        linhas.append(f"DECLARACAO INVALIDA  {d['modulo']}.{d['nome']}  {porque}")
    for e in payload["escopos_invalidos"]:
        linhas.append(f"ESCOPO PENDENTE INVALIDO  {e['prefixo']!r}  {e['por_que']}")

    rodape = [""]
    por_que = {d["por_que"] for d in payload["declaracoes_obsoletas"]}
    if "ganhou_chamador" in por_que:
        rodape.append("Linha que ganhou chamador o comando abaixo resolve inteiro:")
    rodape.append(f"    {payload['comando']}")
    if "alvo_sumiu" in por_que:
        # O sync nunca apaga motivo escrito: só marca `obsoleta: true`. Prometer verde aqui seria instrução
        # impossível de seguir (no porte de origem a mensagem prometia os dois casos).
        rodape.append("Linha de alvo sumido ele so marca `obsoleta: true`: recolar a linha no nome novo, ou apaga-la "
                      "a mao se o simbolo saiu de proposito.")
    if payload["orfaos_nao_declarados"]:
        rodape += ["", ("Orfao novo ele NAO resolve sozinho: entra com motivo vazio e a suite segue vermelha. Falta "
                        "escrever em tools/orfaos.json por que o simbolo existe sem chamador (categoria e motivo; "
                        "RESERVA_DECLARADA tambem com `gatilho`), ou ligar o chamador, ou apagar o simbolo.")]
    return "\n".join(linhas + rodape)


def render(payload: dict) -> str:
    linhas = [(f"orfaos: {payload['total']} simbolos publicos (topo e metodo) | {payload['vivas']} vivos | "
               f"{payload['raizes']} raizes | {payload['declaradas']} declarados"), ""]
    decisao = sum(n for c, n in payload["por_categoria"].items() if CATEGORIAS.get(c) == "decisao")
    divida = sum(n for c, n in payload["por_categoria"].items() if CATEGORIAS.get(c) == "divida")
    linhas.append(f"  decisao declarada  {decisao:4}")
    linhas.append(f"  divida (ORFAO)     {divida:4}")
    for c in sorted(payload["por_categoria"]):
        linhas.append(f"      {c:20} {payload['por_categoria'][c]:4}")
    for e in payload["escopos_pendentes"]:
        n = sum(1 for o in payload["pendentes"] if o["arquivo"].startswith(e["prefixo"] or "\0"))
        linhas.append(f"  pendente {e['prefixo']}: {n} sem chamador, nao julgados (gatilho: {e['gatilho']})")
    linhas.append("")
    linhas.append(mensagem_de_falha(payload) if not payload["ready"] else "[OK] nenhum orfao nao declarado")
    return "\n".join(linhas)


def main(argv=None) -> int:
    p = argparse.ArgumentParser(description="Guarda de orfao: simbolo publico sem raiz de producao.")
    p.add_argument("--raiz", default=None, help="raiz do repositorio (default: a deste arquivo)")
    p.add_argument("--report", action="store_true", help="saida legivel em vez de JSON")
    p.add_argument("--sync", action="store_true", help="sincroniza tools/orfaos.json")
    args = p.parse_args(argv)

    raiz = Path(args.raiz).resolve() if args.raiz else Path(__file__).resolve().parent.parent
    if args.sync:
        print(json.dumps(sincronizar(raiz), ensure_ascii=False, indent=1))
        return 0
    payload = conferir(raiz)
    print(render(payload) if args.report else json.dumps(payload, ensure_ascii=False, indent=1))
    return 0 if payload["ready"] else 1


if __name__ == "__main__":
    # O relatório ecoa motivo escrito à mão, com acento; num console cp1252 isso levantaria UnicodeEncodeError.
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    raise SystemExit(main())
