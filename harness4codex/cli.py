from __future__ import annotations

import argparse
import json
import os
from collections.abc import Sequence
from pathlib import Path

from .arsenal import ArsenalError, ArsenalRegistry
from .branches import BranchKeeper, BranchPolicyError
from .conformance import build_capability_report
from .contract import ContractSnapshot
from .diagnostics import run_doctor
from .graph_context import collect_graph_context, write_graph_context
from .harness_lite_adapter import (
    HarnessLiteClient,
    build_task_envelope,
    execution_is_enabled,
    git_base_revision,
)
from .memory import HarnessMemoryStore, MemoryConsolidator
from .memory_compression import CompressionError, compress_memory_file
from .state import HarnessStateStore, list_session_states
from .state_db import HarnessDatabase, StateTransitionError
from .workflow import load_workflow
from .wiki import WikiIndex


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
    memory_compress = memory_sub.add_parser("compress", help="Compress an eligible secondary memory file.")
    memory_compress.add_argument("path", type=Path)
    memory_compress.add_argument("--dry-run", action="store_true")
    memory_compress.set_defaults(func=_cmd_memory_compress)

    wiki = subparsers.add_parser("wiki", help="Build and query the AI-Brain wiki index.")
    wiki_sub = wiki.add_subparsers(dest="wiki_command", required=True)
    wiki_build = wiki_sub.add_parser("build")
    wiki_build.add_argument("--root", type=Path, required=True)
    wiki_build.set_defaults(func=_cmd_wiki_build)
    wiki_query = wiki_sub.add_parser("query")
    wiki_query.add_argument("query")
    wiki_query.add_argument("--root", type=Path, required=True)
    wiki_query.add_argument("--top-k", type=int, default=5)
    wiki_query.set_defaults(func=_cmd_wiki_query)

    contract = subparsers.add_parser("contract", help="Inspect Harness4Contract conformance.")
    contract_sub = contract.add_subparsers(dest="contract_command", required=True)
    contract_check = contract_sub.add_parser("check")
    contract_check.add_argument("--root", type=Path, default=Path(__file__).resolve().parents[1])
    contract_check.add_argument("--json", action="store_true")
    contract_check.set_defaults(func=_cmd_contract_check)

    branch = subparsers.add_parser("branch", help="Manage persistent conversation branches.")
    branch_sub = branch.add_subparsers(dest="branch_command", required=True)
    branch_offer = branch_sub.add_parser("offer")
    branch_offer.add_argument("--home", type=Path, required=True)
    branch_offer.add_argument("--task", required=True)
    branch_offer.add_argument("--name", required=True)
    branch_offer.add_argument("--topic", required=True)
    branch_offer.add_argument("--turn", type=int, required=True)
    branch_offer.set_defaults(func=_cmd_branch_offer)
    branch_approve = branch_sub.add_parser("approve")
    branch_approve.add_argument("--home", type=Path, required=True)
    branch_approve.add_argument("--branch", required=True)
    branch_approve.set_defaults(func=_cmd_branch_approve)
    branch_open = branch_sub.add_parser("open")
    branch_open.add_argument("--home", type=Path, required=True)
    branch_open.add_argument("--branch", required=True)
    branch_open.add_argument("--seed", type=Path, required=True)
    branch_open.add_argument("--session", help="Codex session id to fork; defaults to --last.")
    branch_open.set_defaults(func=_cmd_branch_open)
    branch_list = branch_sub.add_parser("list")
    branch_list.add_argument("--home", type=Path, required=True)
    branch_list.add_argument("--task", required=True)
    branch_list.set_defaults(func=_cmd_branch_list)
    branch_recall = branch_sub.add_parser("recall")
    branch_recall.add_argument("--home", type=Path, required=True)
    branch_recall.add_argument("--branch", required=True)
    branch_recall.set_defaults(func=_cmd_branch_recall)
    branch_close = branch_sub.add_parser("close")
    branch_close.add_argument("--home", type=Path, required=True)
    branch_close.add_argument("--branch", required=True)
    branch_close.add_argument("--conclusion", required=True)
    branch_close.set_defaults(func=_cmd_branch_close)

    graph = subparsers.add_parser("graph", help="Create Graphify context artifacts.")
    graph_sub = graph.add_subparsers(dest="graph_command", required=True)
    graph_context = graph_sub.add_parser("context")
    graph_context.add_argument("--repo", type=Path, default=Path.cwd())
    graph_context.add_argument("--task", required=True)
    graph_context.add_argument("--scope", required=True)
    graph_context.add_argument("--query", required=True)
    graph_context.add_argument("--output", type=Path)
    graph_context.set_defaults(func=_cmd_graph_context)

    arsenal = subparsers.add_parser("arsenal", help="Inspect the capability registry.")
    arsenal_sub = arsenal.add_subparsers(dest="arsenal_command", required=True)
    arsenal_check = arsenal_sub.add_parser("check")
    arsenal_check.add_argument("--registry", type=Path, required=True)
    arsenal_check.add_argument("--budget", type=int, default=12)
    arsenal_check.set_defaults(func=_cmd_arsenal_check)
    arsenal_overlap = arsenal_sub.add_parser("overlap")
    arsenal_overlap.add_argument("--registry", type=Path, required=True)
    arsenal_overlap.add_argument("--capability", action="append", required=True)
    arsenal_overlap.set_defaults(func=_cmd_arsenal_overlap)

    doctor = subparsers.add_parser("doctor", help="Check Codex workflow and MCP readiness.")
    doctor.add_argument("--home", type=Path, default=Path.home() / ".codex")
    doctor.add_argument("--json", action="store_true")
    doctor.set_defaults(func=_cmd_doctor)

    classification = subparsers.add_parser("classification", help="Confirm or override task classification.")
    classification_sub = classification.add_subparsers(dest="classification_command", required=True)
    classification_confirm = classification_sub.add_parser("confirm")
    classification_confirm.add_argument("--home", type=Path, required=True)
    classification_confirm.add_argument("--task", required=True)
    classification_confirm.add_argument("--tier", choices=["L0", "L1", "L2"], required=True)
    classification_confirm.add_argument(
        "--kind",
        choices=["question", "feature", "bug", "refactor", "architecture", "review", "docs"],
        required=True,
    )
    classification_confirm.add_argument("--confidence", type=float, required=True)
    classification_confirm.add_argument("--source", choices=["semantic", "human_override"], default="semantic")
    classification_confirm.set_defaults(func=_cmd_classification_confirm)

    task = subparsers.add_parser("task", help="Drive the transactional task state machine.")
    task_sub = task.add_subparsers(dest="task_command", required=True)
    task_transition = task_sub.add_parser("transition")
    task_transition.add_argument("--home", type=Path, required=True)
    task_transition.add_argument("--task", required=True)
    task_transition.add_argument("--to", required=True)
    task_transition.add_argument("--expect-revision", type=int, required=True)
    task_transition.set_defaults(func=_cmd_task_transition)
    task_complete = task_sub.add_parser("complete")
    task_complete.add_argument("--home", type=Path, required=True)
    task_complete.add_argument("--task", required=True)
    task_complete.add_argument("--expect-revision", type=int, required=True)
    task_complete.set_defaults(func=_cmd_task_complete)

    artifact = subparsers.add_parser("artifact", help="Record a phase artifact.")
    artifact_sub = artifact.add_subparsers(dest="artifact_command", required=True)
    artifact_record = artifact_sub.add_parser("record")
    artifact_record.add_argument("--home", type=Path, required=True)
    artifact_record.add_argument("--task", required=True)
    artifact_record.add_argument("--type", required=True)
    artifact_record.add_argument("--path", required=True)
    artifact_record.add_argument("--hash", dest="content_hash")
    artifact_record.set_defaults(func=_cmd_artifact_record)

    evidence = subparsers.add_parser("evidence", help="Record revision-bound verification evidence.")
    evidence_sub = evidence.add_subparsers(dest="evidence_command", required=True)
    evidence_record = evidence_sub.add_parser("record")
    evidence_record.add_argument("--home", type=Path, required=True)
    evidence_record.add_argument("--task", required=True)
    evidence_record.add_argument("--type", required=True)
    evidence_record.add_argument("--command", dest="evidence_command_text")
    evidence_record.add_argument("--exit-code", type=int)
    evidence_record.add_argument("--tests-collected", type=int)
    evidence_record.add_argument("--tests-passed", type=int)
    evidence_record.add_argument("--output-hash")
    evidence_record.set_defaults(func=_cmd_evidence_record)

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


def _cmd_memory_compress(args: argparse.Namespace) -> int:
    try:
        report = compress_memory_file(args.path, dry_run=args.dry_run)
    except (CompressionError, OSError) as exc:
        print(f"memory compression failed: {exc}")
        return 2
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0


def _cmd_wiki_build(args: argparse.Namespace) -> int:
    report = WikiIndex(args.root).rebuild()
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0 if report["pages"] > 0 else 1


def _cmd_wiki_query(args: argparse.Namespace) -> int:
    result = WikiIndex(args.root).query(args.query, top_k=args.top_k)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if result["available"] else 1


def _cmd_contract_check(args: argparse.Namespace) -> int:
    report = build_capability_report(args.root)
    if args.json:
        print(json.dumps(report, ensure_ascii=False, indent=2))
    else:
        print(f"Harness4Contract {report['contract_version']}: {'conformant' if report['conformant'] else 'degraded'}")
        for capability, item in report["capabilities"].items():
            print(f"[{item['status']}] {capability}: {', '.join(item['evidence'])}")
    return 0 if report["conformant"] else 1


def _branch_keeper(home: Path) -> BranchKeeper:
    return BranchKeeper(HarnessDatabase(home))


def _run_branch(action) -> int:
    try:
        result = action()
    except (BranchPolicyError, StateTransitionError) as exc:
        print(f"branch operation failed: {exc}")
        return 2
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


def _cmd_branch_offer(args: argparse.Namespace) -> int:
    return _run_branch(lambda: _branch_keeper(args.home).offer(args.task, args.name, args.topic, turn=args.turn))


def _cmd_branch_approve(args: argparse.Namespace) -> int:
    return _run_branch(lambda: _branch_keeper(args.home).approve(args.branch))


def _cmd_branch_open(args: argparse.Namespace) -> int:
    return _run_branch(
        lambda: _branch_keeper(args.home).open(
            args.branch,
            seed_path=args.seed,
            session_id=args.session,
        )
    )


def _cmd_branch_list(args: argparse.Namespace) -> int:
    return _run_branch(lambda: _branch_keeper(args.home).list(args.task))


def _cmd_branch_recall(args: argparse.Namespace) -> int:
    return _run_branch(lambda: _branch_keeper(args.home).recall(args.branch))


def _cmd_branch_close(args: argparse.Namespace) -> int:
    return _run_branch(lambda: _branch_keeper(args.home).close(args.branch, args.conclusion))


def _cmd_graph_context(args: argparse.Namespace) -> int:
    artifact = collect_graph_context(
        args.repo,
        task_id=args.task,
        scope_id=args.scope,
        query=args.query,
    )
    if args.output:
        write_graph_context(args.output, artifact)
    print(json.dumps(artifact, ensure_ascii=False, indent=2))
    return 0


def _cmd_arsenal_check(args: argparse.Namespace) -> int:
    report = ArsenalRegistry(args.registry, budget=args.budget).check()
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0 if report["ok"] else 1


def _cmd_arsenal_overlap(args: argparse.Namespace) -> int:
    try:
        result = ArsenalRegistry(args.registry).overlap(args.capability)
    except ArsenalError as exc:
        print(f"arsenal overlap failed: {exc}")
        return 2
    print(json.dumps(result, ensure_ascii=False, indent=2))
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


def _cmd_classification_confirm(args: argparse.Namespace) -> int:
    contract = ContractSnapshot.load()
    try:
        task = HarnessDatabase(args.home).confirm_classification(
            args.task,
            tier=args.tier,
            kind=args.kind,
            pipeline=contract.pipeline(args.tier, args.kind),
            source=args.source,
            confidence=args.confidence,
        )
    except StateTransitionError as exc:
        print(f"classification confirmation failed: {exc}")
        return 2
    _sync_task_projection(args.home, task, classification_source=args.source, confidence=args.confidence)
    print(f"classification confirmed: {args.tier}-{args.kind} ({args.source}, confidence={args.confidence:.2f})")
    return 0


def _cmd_artifact_record(args: argparse.Namespace) -> int:
    try:
        task = HarnessDatabase(args.home).record_artifact(
            args.task, args.type, args.path, args.content_hash
        )
    except StateTransitionError as exc:
        print(f"artifact record failed: {exc}")
        return 2
    _sync_task_projection(args.home, task)
    print(json.dumps(task, ensure_ascii=False, sort_keys=True))
    return 0


def _cmd_task_transition(args: argparse.Namespace) -> int:
    try:
        task = HarnessDatabase(args.home).transition(
            args.task, args.to, expected_revision=args.expect_revision
        )
    except StateTransitionError as exc:
        print(f"task transition failed: {exc}")
        return 2
    _sync_task_projection(args.home, task)
    print(json.dumps(task, ensure_ascii=False, sort_keys=True))
    return 0


def _cmd_evidence_record(args: argparse.Namespace) -> int:
    try:
        task = HarnessDatabase(args.home).record_evidence(
            args.task,
            evidence_type=args.type,
            command=args.evidence_command_text,
            exit_code=args.exit_code,
            tests_collected=args.tests_collected,
            tests_passed=args.tests_passed,
            output_hash=args.output_hash,
        )
    except StateTransitionError as exc:
        print(f"evidence record failed: {exc}")
        return 2
    _sync_task_projection(args.home, task)
    print(json.dumps(task, ensure_ascii=False, sort_keys=True))
    return 0


def _cmd_task_complete(args: argparse.Namespace) -> int:
    try:
        task = HarnessDatabase(args.home).complete(args.task, expected_revision=args.expect_revision)
    except StateTransitionError as exc:
        print(f"task completion failed: {exc}")
        return 2
    _sync_task_projection(args.home, task)
    print(json.dumps(task, ensure_ascii=False, sort_keys=True))
    return 0


def _sync_task_projection(
    home: Path,
    task: dict,
    *,
    classification_source: str | None = None,
    confidence: float | None = None,
) -> None:
    candidates = [home / "state.json"]
    sessions = home / "sessions"
    if sessions.exists():
        candidates.extend(sorted(sessions.glob("*/state.json")))
    for state_path in candidates:
        if not state_path.exists():
            continue
        try:
            projection = json.loads(state_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        if projection.get("task_id") != task["task_id"]:
            continue
        projection.update(
            {
                "tier": task["tier"],
                "kind": task["kind"],
                "pipeline": task["pipeline"],
                "current_step": task["phase"],
                "status": task["status"],
                "revision": task["revision"],
                "code_revision": task["code_revision"],
                "owner_epoch": task["owner_epoch"],
                "pending_gate": task["pending_gate"],
                "verified": task["verified"],
            }
        )
        if classification_source:
            classification = projection.setdefault("classification", {})
            classification.update(
                {
                    "tier": task["tier"],
                    "kind": task["kind"],
                    "pipeline": task["pipeline"],
                    "source": classification_source,
                    "confidence": confidence,
                }
            )
        store = HarnessStateStore(
            state_path.parent,
            scope=projection.get("scope"),
            memory_home=home,
        )
        store.save(projection)
        return


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
