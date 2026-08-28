from __future__ import annotations

from dataclasses import dataclass

from .command_policy import evaluate_command


@dataclass(frozen=True)
class GuardDecision:
    blocked: bool
    reason: str = ""
    warning: str | None = None


def inspect_command(command: str) -> GuardDecision:
    decision = evaluate_command(command)
    if decision.action == "deny":
        return GuardDecision(blocked=True, reason=f"Blocked dangerous command: {decision.reason}.")
    if decision.action == "require_approval":
        return GuardDecision(blocked=True, reason=f"Command requires explicit approval: {decision.reason}.")
    if decision.action == "unknown":
        return GuardDecision(blocked=True, reason=f"Command could not be safely parsed: {decision.reason}.")
    if decision.action == "warn":
        return GuardDecision(blocked=False, warning=decision.reason)
    return GuardDecision(blocked=False)
