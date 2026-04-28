from __future__ import annotations

import argparse
from pathlib import Path
from typing import Sequence

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
