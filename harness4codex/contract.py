from __future__ import annotations

import hashlib
import json
import os
import sys
from pathlib import Path
from typing import Any


class ContractSnapshotError(ValueError):
    pass


CODEX_ALIASES = {
    "C0": ("L0", "question"),
    "C1": ("L1", "bug"),
    "C2": ("L1", "feature"),
    "C3": ("L2", "architecture"),
    "CR": ("L1", "review"),
    "DOCS": ("L1", "docs"),
}

KIND_ALIASES = {"api-docs": "docs", "documentation": "docs", "escalated-edit": "bug"}


def _mh_pelo_marcador() -> None:
    """Poe no `sys.path` a raiz que `~/.master-harness/mh-root` declara, se ela existir.

    E o protocolo do ecossistema para achar o `mh` sem depender de ele estar
    instalado — o mesmo de `spool_mirror._mh()`. Ate 2026-10-07 este modulo so
    tentava `import mh`, e o Python do sistema (o `python` puro dos hooks) tinha
    um `master-harness` editavel apontando para um worktree apagado: o Codex lia
    o vizinho 1.1.0 com a flag em `preferido` e a canonica em 1.2.0.

    Sem marcador, nada muda e o `import mh` de baixo decide, como antes. E o caso
    do kit S1 do master-harness, que roda este modulo com `-I` e a casa no
    temporario.
    """
    casa = os.environ.get("MASTER_HARNESS_HOME") or os.path.join(os.path.expanduser("~"), ".master-harness")
    try:
        with open(os.path.join(casa, "mh-root"), encoding="utf-8") as fh:
            raiz = fh.readline(4096).strip()
    except OSError:
        return
    if raiz and os.path.isdir(raiz) and raiz not in sys.path:
        sys.path.insert(0, raiz)


def arvore_do_contrato() -> tuple[Path, str]:
    """Devolve (arvore, origem): de onde o contrato foi lido, e por que dali.

    Ate 2026-09-05 a arvore era sempre a copia adjacente
    (`Path(__file__).parent / '_contract'`). Havia onze arvores de contrato na
    maquina e nenhuma linha de codigo elegendo dona — cada programa se amarrava
    a vizinha por `__file__`, sem script de sincronizacao entre elas.

    Agora prefere a canonica declarada no `master-harness`, mas **cai no vizinho
    em qualquer tropeco**: `mh` nao instalado, flag em `vizinho`, canonica
    ausente. Dependencia dura sobre o `mh` seria trocar duplicidade por
    fragilidade, e quem instala este plugin numa maquina limpa nao tem
    `master-harness`.

    A origem viaja junto de proposito: cair para o vizinho em silencio deixaria
    dois relatorios indistinguiveis, e a diferenca entre eles e exatamente o que
    esta migracao muda.
    """
    vizinho = Path(__file__).parent / "_contract"
    try:
        _mh_pelo_marcador()
        from mh import contrato as _mh_contrato
        from mh import flags as _mh_flags

        if _mh_flags.get("contrato") == "vizinho":
            return vizinho, "vizinho:flag"
        if (_mh_contrato.CANONICA / "capabilities.json").is_file():
            return _mh_contrato.CANONICA, "mh"
        return vizinho, "vizinho:canonica-ausente"
    except Exception as exc:  # noqa: BLE001 - o fallback nao pode ter buraco
        return vizinho, f"vizinho:{type(exc).__name__}"


class ContractSnapshot:
    def __init__(self, root: Path, origem: str = "explicita"):
        self.root = root.resolve()
        self.origem = origem
        self.capabilities = self._load("capabilities.json")
        self.pipelines = self._load("pipelines.json")
        self.lock = self._load("contract.lock.json")

    @classmethod
    def load(cls) -> ContractSnapshot:
        arvore, origem = arvore_do_contrato()
        return cls(arvore, origem)

    @property
    def version(self) -> str:
        return str(self.capabilities["contract_version"])

    @property
    def required_capabilities(self) -> tuple[str, ...]:
        return tuple(
            str(item["id"])
            for item in self.capabilities.get("capabilities", [])
            if isinstance(item, dict) and item.get("level") == "required"
        )

    def normalize(self, level: str, kind: str | None = None) -> dict[str, str]:
        raw_level = str(level).strip().upper()
        raw_kind = str(kind or "").strip().lower()
        normalized_kind = KIND_ALIASES.get(raw_kind, raw_kind)
        if raw_level in CODEX_ALIASES:
            tier, default_kind = CODEX_ALIASES[raw_level]
            return {"tier": tier, "kind": normalized_kind or default_kind}
        if "-" in raw_level:
            tier, compound_kind = raw_level.split("-", 1)
            if tier in {"L0", "L1", "L2"}:
                return {"tier": tier, "kind": KIND_ALIASES.get(compound_kind.lower(), compound_kind.lower())}
        if raw_level in {"L0", "L1", "L2"} and normalized_kind:
            return {"tier": raw_level, "kind": normalized_kind}
        raise ContractSnapshotError(f"unsupported classification: {level!r}/{kind!r}")

    def pipeline(self, tier: str, kind: str) -> list[str]:
        key = f"{tier.strip().upper()}-{kind.strip().lower()}"
        value = (self.pipelines.get("pipelines") or {}).get(key)
        if not isinstance(value, list) or not all(isinstance(step, str) for step in value):
            raise ContractSnapshotError(f"undefined contract pipeline: {key}")
        return value.copy()

    def pipeline_fingerprint(self) -> str:
        canonical = json.dumps(
            self.pipelines.get("pipelines") or {},
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        )
        return hashlib.sha256(canonical.encode("utf-8")).hexdigest()

    def verify_lock(self) -> bool:
        expected_files = self.lock.get("files")
        if not isinstance(expected_files, list):
            return False
        digest = hashlib.sha256()
        for relative in expected_files:
            path = self.root / str(relative)
            if not path.is_file():
                return False
            canonical = Path(str(relative)).as_posix()
            digest.update(canonical.encode("utf-8"))
            digest.update(b"\0")
            digest.update(_snapshot_bytes(path))
            digest.update(b"\0")
        return digest.hexdigest() == self.lock.get("sha256") and self.lock.get("contract_version") == self.version

    def capability_report(self, evidence: dict[str, list[str]]) -> dict[str, Any]:
        return {
            "contract_version": self.version,
            # De qual arvore este relatorio saiu. Sem isto, um relatorio lido da
            # canonica e um lido do vizinho sao indistinguiveis — e a diferenca
            # entre os dois e justamente o que esta migracao muda.
            "contract_origem": self.origem,
            "adapter": "harness4codex",
            "capabilities": {
                capability: {
                    "status": "native" if capability in evidence else "degraded",
                    "evidence": evidence.get(capability, ["missing conformance evidence"]),
                }
                for capability in self.required_capabilities
            },
        }

    def _load(self, relative: str) -> dict[str, Any]:
        path = self.root / relative
        try:
            value = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            raise ContractSnapshotError(f"invalid contract snapshot file {path}: {exc}") from exc
        if not isinstance(value, dict):
            raise ContractSnapshotError(f"contract snapshot file must be an object: {path}")
        return value


def _snapshot_bytes(path: Path) -> bytes:
    if path.suffix.lower() != ".json":
        return path.read_bytes()
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ContractSnapshotError(f"invalid contract snapshot file {path}: {exc}") from exc
    return json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
