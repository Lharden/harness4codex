from __future__ import annotations

import hashlib
import json
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
