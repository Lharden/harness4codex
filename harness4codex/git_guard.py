from __future__ import annotations

from dataclasses import dataclass
import re


@dataclass(frozen=True)
class GuardDecision:
    blocked: bool
    reason: str = ""
    warning: str | None = None


BLOCK_RULES: list[tuple[re.Pattern[str], str]] = [
    (re.compile(r"\bgit\s+push\b[^\n]*--force(?:-with-lease)?\b", re.IGNORECASE), "Blocked dangerous git force push."),
    (re.compile(r"\bgit\s+reset\s+--hard\b", re.IGNORECASE), "Blocked dangerous git reset --hard."),
    (re.compile(r"\bgit\s+clean\b[^\n]*-[a-zA-Z]*f[a-zA-Z]*\b", re.IGNORECASE), "Blocked dangerous git clean with force flag."),
    (re.compile(r"\bgit\s+branch\b[^\n]*-[a-zA-Z]*D\b", re.IGNORECASE), "Blocked dangerous forced branch deletion."),
    (re.compile(r"\bgit\s+(checkout|restore)\s+\.\s*$", re.IGNORECASE), "Blocked broad checkout/restore of the whole workspace."),
]


def inspect_command(command: str) -> GuardDecision:
    command = command or ""
    for pattern, reason in BLOCK_RULES:
        if pattern.search(command):
            return GuardDecision(blocked=True, reason=reason)

    if re.search(r"\bgit\s+push\b", command, re.IGNORECASE):
        return GuardDecision(
            blocked=False,
            warning="Git push requested. Confirm branch, remote, and reviewed diff before publishing.",
        )

    return GuardDecision(blocked=False)
