from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any


class ArsenalError(ValueError):
    pass


class ArsenalRegistry:
    def __init__(self, path: str | Path, *, budget: int = 12):
        self.path = Path(path)
        self.budget = max(int(budget), 0)

    def _load(self) -> dict[str, Any]:
        if not self.path.exists():
            return {"schema_version": 1, "capabilities": [], "tools": {}}
        try:
            payload = json.loads(self.path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            raise ArsenalError(f"invalid arsenal registry: {exc}") from exc
        if not isinstance(payload, dict):
            raise ArsenalError("arsenal registry root must be an object")
        return payload

    def _save(self, payload: dict[str, Any]) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        temporary = self.path.with_suffix(self.path.suffix + ".tmp")
        temporary.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        os.replace(temporary, self.path)

    def define_capabilities(self, names: list[str]) -> None:
        normalized = sorted({name.strip() for name in names if name.strip()})
        payload = self._load()
        payload["capabilities"] = normalized
        self._save(payload)

    def add_tool(
        self,
        name: str,
        capabilities: list[str],
        *,
        status: str,
        absorbed_into: str | Path | None = None,
    ) -> None:
        if status not in {"adopted", "absorbed", "trial"}:
            raise ArsenalError(f"unsupported status: {status}")
        payload = self._load()
        vocabulary = set(payload.get("capabilities") or [])
        unknown = sorted(set(capabilities) - vocabulary)
        if unknown:
            raise ArsenalError(f"capability outside vocabulary: {unknown}")
        destination = None
        if status == "absorbed":
            if absorbed_into is None or not Path(absorbed_into).exists():
                raise ArsenalError("absorbed capability requires an existing destination")
            destination = str(Path(absorbed_into).resolve())
        payload.setdefault("tools", {})[name] = {
            "status": status,
            "capabilities": sorted(set(capabilities)),
            "absorbed_into": destination,
        }
        active = [tool for tool in payload["tools"].values() if tool.get("status") in {"adopted", "trial"}]
        if len(active) > self.budget:
            raise ArsenalError(f"arsenal budget exceeded: {len(active)}/{self.budget}")
        self._save(payload)

    def overlap(self, capabilities: list[str]) -> list[str]:
        payload = self._load()
        vocabulary = set(payload.get("capabilities") or [])
        unknown = sorted(set(capabilities) - vocabulary)
        if unknown:
            raise ArsenalError(f"capability outside vocabulary: {unknown}")
        requested = set(capabilities)
        return sorted(
            name
            for name, tool in payload.get("tools", {}).items()
            if requested.intersection(tool.get("capabilities") or [])
        )

    def budget_report(self) -> dict[str, int | bool]:
        payload = self._load()
        used = sum(
            1 for tool in payload.get("tools", {}).values() if tool.get("status") in {"adopted", "trial"}
        )
        return {"budget": self.budget, "used": used, "available": max(self.budget - used, 0), "fits": used <= self.budget}

    def check(self) -> dict[str, Any]:
        payload = self._load()
        errors: list[str] = []
        vocabulary = set(payload.get("capabilities") or [])
        for name, tool in payload.get("tools", {}).items():
            unknown = set(tool.get("capabilities") or []) - vocabulary
            if unknown:
                errors.append(f"{name}: unknown capabilities {sorted(unknown)}")
            if tool.get("status") == "absorbed":
                target = tool.get("absorbed_into")
                if not target or not Path(target).exists():
                    errors.append(f"{name}: absorbed destination missing")
        report = self.budget_report()
        if not report["fits"]:
            errors.append("arsenal budget exceeded")
        return {"ok": not errors, "errors": errors, "budget": report}
