from __future__ import annotations

import re
import shutil
from pathlib import Path
from typing import Any


class CompressionError(ValueError):
    pass


PROTECTED_NAMES = {"agents.md", "memory.md", "core-memories.md", "claude.md"}
SPEC_MARKERS = ("[NEEDS CLARIFICATION", "Given", "When", "Then")
FILLERS = (
    r"\bbasically,?\s*",
    r"\bactually\b\s*",
    r"\breally\b\s*",
    r"\bI think\s*",
    r"\bI believe\s*",
    r"\bbasicamente,?\s*",
    r"\bna verdade,?\s*",
    r"\brealmente\b\s*",
    r"\beu acho que\s*",
)


def compress_memory_file(path: str | Path, *, dry_run: bool = False) -> dict[str, Any]:
    target = Path(path)
    if target.name.casefold() in PROTECTED_NAMES or "docs/specs" in target.as_posix().casefold():
        raise CompressionError(f"protected memory file: {target}")
    text = target.read_text(encoding="utf-8")
    if re.search(r"\bREQ-\d+\b", text) or all(marker in text for marker in ("Given", "When", "Then")) or any(
        marker in text for marker in SPEC_MARKERS[:1]
    ):
        raise CompressionError("specification markers make this file protected")
    output = _compress(text)
    report = {
        "path": str(target),
        "input_chars": len(text),
        "output_chars": len(output),
        "saved_chars": len(text) - len(output),
        "dry_run": dry_run,
    }
    if dry_run or output == text:
        return report
    backup = target.with_name(f"{target.stem}.original{target.suffix}")
    if not backup.exists():
        shutil.copy2(target, backup)
    target.write_text(output, encoding="utf-8")
    report["backup"] = str(backup)
    return report


def _compress(text: str) -> str:
    in_code = False
    output: list[str] = []
    for line in text.splitlines(keepends=True):
        if line.lstrip().startswith("```"):
            in_code = not in_code
            output.append(line)
            continue
        stripped = line.lstrip()
        protected = in_code or stripped.startswith(("#", "-", "*", "|", ">", "$")) or "`" in line
        if protected:
            output.append(line)
            continue
        compressed = line
        for pattern in FILLERS:
            compressed = re.sub(pattern, "", compressed, flags=re.IGNORECASE)
        compressed = re.sub(r" {2,}", " ", compressed)
        compressed = re.sub(r"^\s*,\s*", "", compressed)
        if compressed and compressed[0].islower() and line[:1].isupper():
            compressed = compressed[0].upper() + compressed[1:]
        output.append(compressed)
    return "".join(output)
