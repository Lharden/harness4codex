from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any
import re


WORKFLOW_FILENAME = "WORKFLOW.md"


class WorkflowConfigError(ValueError):
    pass


@dataclass(frozen=True)
class WorkflowDefinition:
    path: Path
    config: dict[str, Any] = field(default_factory=dict)
    prompt_template: str = ""

    @property
    def verification_commands(self) -> list[str]:
        verification = self.config.get("verification")
        if isinstance(verification, dict):
            commands = verification.get("commands") or []
            if isinstance(commands, list):
                return [str(command) for command in commands]
        commands = self.config.get("verification_commands") or []
        if isinstance(commands, list):
            return [str(command) for command in commands]
        return []

    @property
    def active_states(self) -> list[str]:
        orchestration = self.config.get("orchestration")
        if isinstance(orchestration, dict):
            states = orchestration.get("active_states") or []
            if isinstance(states, list) and states:
                return [str(state) for state in states]
        return ["Todo", "In Progress", "Ready"]

    @property
    def terminal_states(self) -> list[str]:
        orchestration = self.config.get("orchestration")
        if isinstance(orchestration, dict):
            states = orchestration.get("terminal_states") or []
            if isinstance(states, list) and states:
                return [str(state) for state in states]
        return ["Done", "Canceled", "Cancelled"]

    @property
    def max_turns(self) -> int:
        orchestration = self.config.get("orchestration")
        if isinstance(orchestration, dict):
            value = orchestration.get("max_turns")
            if isinstance(value, int) and value > 0:
                return value
        return 5

    @property
    def handoff_state(self) -> str:
        value = self.config.get("handoff_state")
        if value:
            return str(value)
        orchestration = self.config.get("orchestration")
        if isinstance(orchestration, dict) and orchestration.get("handoff_state"):
            return str(orchestration["handoff_state"])
        return "Human Review"

    def render_for_prompt(self, max_body_chars: int = 1200) -> str:
        relative = self.path.name
        lines = [
            "Repo WORKFLOW.md",
            f"Path: {relative}",
            f"Active states: {', '.join(self.active_states)}",
            f"Terminal states: {', '.join(self.terminal_states)}",
            f"Handoff state: {self.handoff_state}",
        ]
        commands = self.verification_commands
        if commands:
            lines.append("Verification commands: " + "; ".join(commands))
        body = self.prompt_template.strip()
        if body:
            if len(body) > max_body_chars:
                body = body[: max_body_chars - 15].rstrip() + "\n...[truncated]"
            lines.extend(["Workflow body:", body])
        return "\n".join(lines)


def find_workflow(start: str | Path | None = None) -> Path | None:
    current = Path(start or Path.cwd()).resolve()
    if current.is_file():
        current = current.parent
    for directory in [current, *current.parents]:
        candidate = directory / WORKFLOW_FILENAME
        if candidate.exists():
            return candidate
        if (directory / ".git").exists():
            break
    return None


def load_workflow(start: str | Path | None = None) -> WorkflowDefinition | None:
    path = find_workflow(start)
    if path is None:
        return None
    text = path.read_text(encoding="utf-8")
    config, body = _split_frontmatter(text)
    return WorkflowDefinition(path=path, config=config, prompt_template=body.strip())


def _split_frontmatter(text: str) -> tuple[dict[str, Any], str]:
    lines = text.splitlines()
    if not lines or lines[0].strip() != "---":
        return {}, text
    end_index = None
    for index in range(1, len(lines)):
        if lines[index].strip() == "---":
            end_index = index
            break
    if end_index is None:
        raise WorkflowConfigError("WORKFLOW.md frontmatter starts with --- but never closes.")
    config = _parse_limited_yaml(lines[1:end_index])
    body = "\n".join(lines[end_index + 1 :])
    return config, body


def _parse_limited_yaml(lines: list[str]) -> dict[str, Any]:
    meaningful = [line.rstrip() for line in lines if line.strip() and not line.lstrip().startswith("#")]
    parsed, index = _parse_block(meaningful, 0, 0)
    if index != len(meaningful):
        raise WorkflowConfigError(f"Unsupported frontmatter near: {meaningful[index]}")
    if not isinstance(parsed, dict):
        raise WorkflowConfigError("WORKFLOW.md frontmatter root must be a mapping.")
    return parsed


def _parse_block(lines: list[str], index: int, indent: int) -> tuple[Any, int]:
    if index >= len(lines):
        return {}, index
    first_indent = _indent_of(lines[index])
    if first_indent < indent:
        return {}, index
    is_list = lines[index].strip().startswith("- ")
    if is_list:
        values: list[Any] = []
        while index < len(lines):
            current_indent = _indent_of(lines[index])
            if current_indent < indent:
                break
            if current_indent > indent:
                raise WorkflowConfigError(f"Unexpected nested list line: {lines[index]}")
            text = lines[index].strip()
            if not text.startswith("- "):
                break
            values.append(_parse_scalar(text[2:].strip()))
            index += 1
        return values, index

    values: dict[str, Any] = {}
    while index < len(lines):
        current_indent = _indent_of(lines[index])
        if current_indent < indent:
            break
        if current_indent > indent:
            raise WorkflowConfigError(f"Unexpected indentation: {lines[index]}")
        text = lines[index].strip()
        match = re.match(r"([^:]+):(.*)$", text)
        if not match:
            raise WorkflowConfigError(f"Unsupported frontmatter line: {lines[index]}")
        key = match.group(1).strip()
        value_text = match.group(2).strip()
        index += 1
        if value_text:
            values[key] = _parse_scalar(value_text)
            continue
        child, index = _parse_block(lines, index, indent + 2)
        values[key] = child
    return values, index


def _indent_of(line: str) -> int:
    return len(line) - len(line.lstrip(" "))


def _parse_scalar(value: str) -> Any:
    if value in {"true", "True"}:
        return True
    if value in {"false", "False"}:
        return False
    if value in {"null", "Null", "~"}:
        return None
    if re.fullmatch(r"-?\d+", value):
        return int(value)
    if value.startswith("[") and value.endswith("]"):
        inner = value[1:-1].strip()
        if not inner:
            return []
        return [_parse_scalar(part.strip()) for part in inner.split(",")]
    if (value.startswith('"') and value.endswith('"')) or (value.startswith("'") and value.endswith("'")):
        return value[1:-1]
    return value
