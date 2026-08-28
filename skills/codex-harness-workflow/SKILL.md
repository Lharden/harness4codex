---
name: codex-harness-workflow
description: Use when HARNESS4CODEX context appears, a task is classified L1/L2/review/docs, a hook requests continuation, or the user asks for Harness4Codex orchestration, SDD, gates, proactive skills, or pipeline recovery.
---

# Harness4Codex Workflow

Harness4Codex is the Codex-native supervisor for classification, SDD artifacts,
transactional progress, evidence and completion. Hook text is a projection; the
SQLite task record is authoritative.

## Start or resume

1. Read `HARNESS4CODEX` context and locate `home`, `task_id`, `revision`, `phase`,
   `tier`, `kind`, `pipeline` and `scope`.
2. Confirm the regex suggestion semantically before the first phase:
   `harness4codex classification confirm --home <home> --task <id> --tier L1|L2 --kind <kind> --confidence <0..1>`.
   Use `--source human_override` when the user chose the class.
3. Resume the current phase. Never skip a phase because its output seems implied.
4. After creating a required artifact, persist it with
   `harness4codex artifact record --home <home> --task <id> --type <type> --path <path> --hash <sha256>`.
5. Advance with optimistic concurrency:
   `harness4codex task transition --home <home> --task <id> --to <phase> --expect-revision <revision>`.

## Canonical execution

- L0 executes directly.
- L1 feature/refactor: `write-spec-light -> tdd -> verify-against-spec`.
- L1 bug: `systematic-debugging -> tdd -> verify`.
- L2 feature: `discuss -> brainstorming -> graph-context -> write-spec -> grill-me -> approve-spec -> design-doc -> validate-plan -> approve-plan -> tdd -> verify-multimodel`.
- L2 architecture/refactor uses the same spec, adversarial, design, plan and evidence gates.
- Review and docs pipelines preserve findings/source selection as first-class phases.

Use the named local skill when one exists. For superpowers phases, invoke the
corresponding installed skill. One acceptance criterion maps to at least one test.

## Human gates

`approve-spec`, `approve-plan`, `answer-clarifications`, `branch-open`, and
`escalation` require an explicit user decision. Ask once with the concrete artifact
or ambiguity. A gate response is recorded through the task state machine; silence is
not approval.

## Delegated work

Use parallel agents only where the active skill or user authorizes delegation and
the nodes are independent. Before dispatch, publish a node census with node id,
role, inputs, output contract and dependencies. Every return must satisfy `NodeResult`:
`node_id`, `status`, `summary`, `artifacts`, `evidence`, `risks`, `questions`.
Reconcile the census with actual returns and inspect the shared-worktree diff before
accepting claims. Missing or duplicate nodes are workflow failures, not implicit success.

## Evidence and completion

Record fresh evidence bound to the current code revision:
`harness4codex evidence record --home <home> --task <id> --type test --command <cmd> --exit-code 0 --tests-collected N --tests-passed N --output-hash <sha256>`.
Zero collected tests never verify a task. Then run
`harness4codex task complete --home <home> --task <id> --expect-revision <revision>`.
Any file mutation invalidates earlier verification.

## Editorial control

Apply `DROP / CONSTRAIN / RETAIN` once before propagating artifacts. DROP removes a
rejected editorial direction from active work and thematic memory; an indispensable
audit keeps only id, location and destination `DROP`. CONSTRAIN keeps persistent
safety, compliance, privacy and format predicates at their boundary. RETAIN keeps a
scientifically necessary limit local to the claim and its evidence.

## Stop and recovery

Automatic continuation is bounded. The third unresolved Stop opens `escalation` and
asks the user. PreCompact writes a handoff projection; PostCompact and resume hooks
reload the same scoped task. Never create a second active task for the same scope.
