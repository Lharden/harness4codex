from __future__ import annotations

import argparse
import json
import os
from collections.abc import Sequence
from pathlib import Path

from .diagnostics import run_doctor
from .harness_lite_adapter import (
    HarnessLiteClient,
    build_task_envelope,
    execution_is_enabled,
    git_base_revision,
)
from .memory import HarnessMemoryStore, MemoryConsolidator
from .state import HarnessStateStore, list_session_states
from .workflow import load_workflow


def run(argv: Sequence[str] | None = None) -> int:
    parser = _build_parser()
    args = parser.parse_args(argv)
    return args.func(args)


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="harness4codex", description="Harness4Codex utility CLI.")
    subparsers = parser.add_subparsers(dest="command", required=True)

    status = subparsers.add_parser("status", help="Show local harness state.")
    status.add_argument("--home", type=Path, default=None)
    status.add_argument("--cwd", type=Path, default=Path.cwd())
    status.set_defaults(func=_cmd_status)

    workflow = subparsers.add_parser("workflow", help="Inspect repo workflow policy.")
    workflow_sub = workflow.add_subparsers(dest="workflow_command", required=True)
    workflow_show = workflow_sub.add_parser("show", help="Render WORKFLOW.md context.")
    workflow_show.add_argument("--cwd", type=Path, default=Path.cwd())
    workflow_show.set_defaults(func=_cmd_workflow_show)

    memory = subparsers.add_parser("memory", help="Search and consolidate harness memory.")
    memory_sub = memory.add_subparsers(dest="memory_command", required=True)
    memory_search = memory_sub.add_parser("search", help="Search harness history.")
    memory_search.add_argument("query")
    memory_search.add_argument("--home", type=Path, default=None)
    memory_search.set_defaults(func=_cmd_memory_search)
    memory_consolidate = memory_sub.add_parser("consolidate", help="Create auditable memory proposals.")
    memory_consolidate.add_argument("--home", type=Path, default=None)
    memory_consolidate.set_defaults(func=_cmd_memory_consolidate)

    doctor = subparsers.add_parser("doctor", help="Check Codex workflow and MCP readiness.")
    doctor.add_argument("--home", type=Path, default=Path.home() / ".codex")
    doctor.add_argument("--json", action="store_true")
    doctor.set_defaults(func=_cmd_doctor)

    lite = subparsers.add_parser("lite", help="Preview or explicitly submit work to Harness Lite.")
    lite_sub = lite.add_subparsers(dest="lite_command", required=True)
    for verb, handler in (("preview", _cmd_lite_preview), ("submit", _cmd_lite_submit)):
        command = lite_sub.add_parser(verb)
        command.add_argument("objective")
        command.add_argument("--level", choices=["C1", "C2", "C3", "CR", "DOCS"], required=True)
        command.add_argument("--cwd", type=Path, default=Path.cwd())
        command.add_argument("--session-id", default="harness4codex-cli")
        command.add_argument("--acceptance", action="append", default=[])
        command.add_argument("--allowed-command", action="append", default=[])
        command.set_defaults(func=handler)

    return parser


def _cmd_status(args: argparse.Namespace) -> int:
    state = HarnessStateStore(args.home).load()
    workflow = load_workflow(args.cwd)
    memory = HarnessMemoryStore(args.home)
    session_states = list_session_states(args.home)
    active_sessions = [session for session in session_states if session.get("status") == "active"]
    print("Harness4Codex status")
    print(f"home: {memory.home}")
    print(f"status: {state.get('status')}")
    print(f"level: {state.get('level')} / {state.get('kind')}")
    print(f"task: {state.get('task_id') or 'none'}")
    print(f"verified: {state.get('verified')}")
    print(f"files touched: {len(state.get('files') or [])}")
    print(f"memory records: {memory.history_count()}")
    print(f"sessions: {len(session_states)}")
    print(f"active sessions: {len(active_sessions)}")
    if workflow:
        print(f"workflow: {workflow.path}")
        commands = workflow.verification_commands
        if commands:
            print("verification: " + "; ".join(commands))
    else:
        print("workflow: none")
    return 0


def _cmd_workflow_show(args: argparse.Namespace) -> int:
    workflow = load_workflow(args.cwd)
    if workflow is None:
        print("No WORKFLOW.md found.")
        return 1
    print(workflow.render_for_prompt())
    return 0


def _cmd_memory_search(args: argparse.Namespace) -> int:
    store = HarnessMemoryStore(args.home)
    results = store.search(args.query)
    if not results:
        print("No memory matches.")
        return 0
    for result in results:
        print(f"{result['created_at']} {result['event']}: {result['text']}")
    return 0


def _cmd_memory_consolidate(args: argparse.Namespace) -> int:
    report = MemoryConsolidator(args.home).consolidate()
    print(f"events read: {report.events_read}")
    if not report.proposals:
        print("proposals: none")
        return 0
    print("proposals:")
    for proposal in report.proposals:
        print(f"- {proposal['key']}: {proposal['value']}")
    return 0


def _cmd_doctor(args: argparse.Namespace) -> int:
    report = run_doctor(args.home)
    if args.json:
        print(json.dumps(report.to_dict(), ensure_ascii=False, indent=2))
    else:
        print(f"Harness4Codex doctor: {'ready' if report.ok else 'not ready'}")
        for check in report.checks:
            print(f"[{check.status}] {check.code}: {check.message}")
    return 0 if report.ok else 1


def _lite_envelope(args: argparse.Namespace, *, max_cost_usd: float) -> dict | None:
    revision = git_base_revision(args.cwd)
    if revision is None:
        print("Harness Lite: the workspace must have a Git HEAD revision.")
        return None
    try:
        runtime = int(os.environ.get("HARNESS4CODEX_LITE_MAX_RUNTIME_SEC", "300"))
    except ValueError:
        runtime = 300
    return build_task_envelope(
        level=args.level,
        objective=args.objective,
        workspace_path=str(args.cwd),
        base_revision=revision,
        session_id=args.session_id,
        acceptance_criteria=args.acceptance or None,
        allowed_commands=args.allowed_command,
        requested_profile=os.environ.get("HARNESS4CODEX_LITE_PROFILE", "auto"),
        data_class=os.environ.get("HARNESS4CODEX_LITE_DATA_CLASS", "internal"),
        max_cost_usd=max_cost_usd,
        max_runtime_sec=max(runtime, 1),
    )


def _lite_client() -> HarnessLiteClient | None:
    client = HarnessLiteClient.from_env()
    if client is None:
        print("Harness Lite: HARNESS_CONTROL_TOKEN is not configured.")
    return client


def _report_lite(result) -> int:
    print(
        json.dumps(
            {
                "ok": result.ok,
                "status": result.status,
                "result": result.result,
                "code": result.code,
                "message": result.message,
            },
            ensure_ascii=False,
            indent=2,
        )
    )
    return 0 if result.ok else 1


def _cmd_lite_preview(args: argparse.Namespace) -> int:
    client = _lite_client()
    if client is None:
        return 2
    try:
        budget = float(os.environ.get("HARNESS4CODEX_LITE_PREVIEW_MAX_COST_USD", "0"))
    except ValueError:
        budget = 0.0
    envelope = _lite_envelope(args, max_cost_usd=max(budget, 0.0))
    return 2 if envelope is None else _report_lite(client.preview(envelope))


def _cmd_lite_submit(args: argparse.Namespace) -> int:
    if not execution_is_enabled():
        print(
            "Harness Lite execution needs explicit opt-in: set HARNESS4CODEX_LITE_EXECUTE=true "
            "and a positive HARNESS4CODEX_LITE_MAX_COST_USD."
        )
        return 2
    client = _lite_client()
    if client is None:
        return 2
    budget = float(os.environ["HARNESS4CODEX_LITE_MAX_COST_USD"])
    envelope = _lite_envelope(args, max_cost_usd=budget)
    return 2 if envelope is None else _report_lite(client.submit(envelope))
