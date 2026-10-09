import io
import json
import sqlite3
import sys
import time

import pytest

from harness4codex import hook
from harness4codex.hook import (
    _decode_payload,
    _extract_exit_code,
    _is_shell_tool,
    _looks_like_verification,
    handle_payload,
)
from harness4codex.memory import HarnessMemoryStore
from harness4codex.state import HarnessStateStore


def _decode(output: str) -> dict:
    assert output
    return json.loads(output)


def _feature_no_tdd(home) -> None:
    """Abre a task de feature pelo prompt e a leva a `tdd` pelos caminhos de producao.

    O Stop so cobra teste da primeira fase de implementacao em diante
    (`tests/test_portao_pre_implementacao.py`); estes testes medem bloqueio,
    schema e escalada, entao posicionam a task onde o bloqueio existe."""
    from harness4codex.cli import _sync_task_projection

    handle_payload({"hook_event_name": "UserPromptSubmit", "prompt": "Implemente exportacao CSV."}, harness_home=home)
    store = HarnessStateStore(home)
    task_id = store.load()["task_id"]
    task = store.database.record_artifact(task_id, "spec-light", "docs/specs/csv-spec-light.md", None)
    task = store.database.transition(task_id, "tdd", expected_revision=task["revision"])
    _sync_task_projection(home, task)


def _run_main(monkeypatch, payload: dict) -> int:
    monkeypatch.setattr(sys, "stdin", io.TextIOWrapper(io.BytesIO(json.dumps(payload).encode("utf-8"))))
    monkeypatch.setattr(sys, "stdout", io.TextIOWrapper(io.BytesIO()))
    return hook.main()


def test_main_records_heartbeat_for_the_event(tmp_path, monkeypatch):
    """B-18: o hook ficou um mes sem rodar e nada no disco dizia isso.

    O heartbeat e o sinal que o doctor confronta com os turnos que o proprio
    Codex registra nos rollouts.
    """
    monkeypatch.setenv("HARNESS4CODEX_HOME", str(tmp_path))
    before = time.time()

    assert _run_main(monkeypatch, {"hook_event_name": "UserPromptSubmit", "prompt": "oi"}) == 0

    beat = float((tmp_path / "heartbeats" / "UserPromptSubmit").read_text(encoding="utf-8"))
    assert before <= beat <= time.time()


def test_main_records_heartbeat_before_handling(tmp_path, monkeypatch):
    """Mede a chamada, nao o trabalho: um handler que quebra ainda foi chamado."""
    monkeypatch.setenv("HARNESS4CODEX_HOME", str(tmp_path))

    def explode(_payload, harness_home=None):
        raise RuntimeError("handler quebrado")

    monkeypatch.setattr(hook, "handle_payload", explode)

    assert _run_main(monkeypatch, {"hook_event_name": "Stop"}) == 0
    assert (tmp_path / "heartbeats" / "Stop").is_file()


def test_user_prompt_submit_injects_harness_context(tmp_path):
    output = handle_payload(
        {
            "hook_event_name": "UserPromptSubmit",
            "prompt": "Implemente exportacao CSV.",
        },
        harness_home=tmp_path,
    )

    data = _decode(output)
    context = data["hookSpecificOutput"]["additionalContext"]
    assert "HARNESS4CODEX" in context
    assert "codex-harness-workflow" in context


def test_user_prompt_submit_includes_repo_workflow_context(tmp_path):
    repo = tmp_path / "repo"
    repo.mkdir()
    (repo / "WORKFLOW.md").write_text(
        "---\nverification:\n  commands:\n    - pytest -q\nhandoff_state: Human Review\n---\n"
        "# Workflow\nAttach proof before review.\n",
        encoding="utf-8",
    )

    output = handle_payload(
        {
            "hook_event_name": "UserPromptSubmit",
            "prompt": "Implemente exportacao CSV.",
            "cwd": str(repo),
        },
        harness_home=tmp_path / "home",
    )

    context = _decode(output)["hookSpecificOutput"]["additionalContext"]
    assert "Repo WORKFLOW.md" in context
    assert "pytest -q" in context
    assert "Human Review" in context


def test_session_start_resumes_active_pipeline(tmp_path):
    handle_payload(
        {"hook_event_name": "UserPromptSubmit", "prompt": "Corrija bug de login."},
        harness_home=tmp_path,
    )

    output = handle_payload({"hook_event_name": "SessionStart", "source": "resume"}, harness_home=tmp_path)

    assert "Retome o pipeline" in _decode(output)["hookSpecificOutput"]["additionalContext"]


def test_session_start_expires_stale_pipeline_before_resuming(tmp_path):
    handle_payload(
        {"hook_event_name": "UserPromptSubmit", "prompt": "Corrija bug de login."},
        harness_home=tmp_path,
    )
    state_path = tmp_path / "state.json"
    state = json.loads(state_path.read_text(encoding="utf-8"))
    state["started_at"] = "2000-01-01T00:00:00+00:00"
    state_path.write_text(json.dumps(state), encoding="utf-8")
    with sqlite3.connect(tmp_path / "harness.db") as connection:
        connection.execute(
            "UPDATE tasks SET started_at = ? WHERE task_id = ?",
            ("2000-01-01T00:00:00+00:00", state["task_id"]),
        )

    output = handle_payload({"hook_event_name": "SessionStart", "source": "resume"}, harness_home=tmp_path)

    assert output == ""
    expired = HarnessStateStore(tmp_path).load()
    assert expired["status"] == "idle"
    assert expired["task_id"] is None


def test_user_response_continues_pending_gate_instead_of_starting_new_task(tmp_path):
    store = HarnessStateStore(tmp_path)
    handle_payload(
        {"hook_event_name": "UserPromptSubmit", "prompt": "Implemente exportacao CSV."},
        harness_home=tmp_path,
    )
    waiting = store.set_pending_gate("approve-plan")

    output = handle_payload(
        {"hook_event_name": "UserPromptSubmit", "prompt": "Aprovo o plano."},
        harness_home=tmp_path,
    )

    current = store.load()
    assert current["task_id"] == waiting["task_id"]
    assert current["status"] == "awaiting_gate"
    context = _decode(output)["hookSpecificOutput"]["additionalContext"]
    assert "approve-plan" in context
    assert "Resolve" in context


def test_parallel_sessions_do_not_continue_each_other(tmp_path):
    repo = tmp_path / "repo"
    repo.mkdir()
    handle_payload(
        {
            "hook_event_name": "UserPromptSubmit",
            "session_id": "session-a",
            "cwd": str(repo),
            "prompt": "Implemente exportacao CSV.",
        },
        harness_home=tmp_path,
    )

    output = handle_payload(
        {
            "hook_event_name": "UserPromptSubmit",
            "session_id": "session-b",
            "cwd": str(repo),
            "prompt": "Explique este modulo.",
        },
        harness_home=tmp_path,
    )

    context = _decode(output)["hookSpecificOutput"]["additionalContext"]
    assert "Classificacao criada" in context
    assert "Continue o pipeline ativo" not in context
    assert "Level: C0 / question" in context


def test_stop_gate_is_scoped_to_session(tmp_path):
    repo = tmp_path / "repo"
    repo.mkdir()
    handle_payload(
        {
            "hook_event_name": "UserPromptSubmit",
            "session_id": "session-a",
            "cwd": str(repo),
            "prompt": "Implemente exportacao CSV.",
        },
        harness_home=tmp_path,
    )

    output = handle_payload(
        {"hook_event_name": "Stop", "session_id": "session-b", "cwd": str(repo)},
        harness_home=tmp_path,
    )

    assert output == ""


def test_pre_tool_use_denies_dangerous_git(tmp_path):
    output = handle_payload(
        {
            "hook_event_name": "PreToolUse",
            "tool_name": "Bash",
            "tool_input": {"command": "git reset --hard HEAD~1"},
        },
        harness_home=tmp_path,
    )

    data = _decode(output)
    assert data["hookSpecificOutput"]["permissionDecision"] == "deny"
    assert set(data) == {"systemMessage", "hookSpecificOutput"}
    assert set(data["hookSpecificOutput"]) == {
        "hookEventName",
        "permissionDecision",
        "permissionDecisionReason",
    }


def test_permission_request_denies_dangerous_git(tmp_path):
    output = handle_payload(
        {
            "hook_event_name": "PermissionRequest",
            "tool_name": "Bash",
            "tool_input": {"command": "git push --force"},
        },
        harness_home=tmp_path,
    )

    data = _decode(output)
    assert data["hookSpecificOutput"]["decision"]["behavior"] == "deny"
    assert set(data) == {"systemMessage", "hookSpecificOutput"}
    assert set(data["hookSpecificOutput"]) == {"hookEventName", "decision"}


def test_permission_request_warning_uses_only_a_generic_system_message(tmp_path):
    output = handle_payload(
        {
            "hook_event_name": "PermissionRequest",
            "tool_name": "Bash",
            "tool_input": {"command": "git push origin feature"},
        },
        harness_home=tmp_path,
    )

    data = _decode(output)
    assert set(data) == {"systemMessage"}
    assert "confirm" in data["systemMessage"].lower()


def test_post_tool_use_promotes_after_multiple_files(tmp_path):
    handle_payload(
        {"hook_event_name": "UserPromptSubmit", "prompt": "Explique este modulo."},
        harness_home=tmp_path,
    )
    output = handle_payload(
        {
            "hook_event_name": "PostToolUse",
            "tool_name": "apply_patch",
            "tool_input": {"command": "*** Update File: a.py\n*** Add File: b.py\n*** Update File: c.py\n"},
        },
        harness_home=tmp_path,
    )

    assert "promoted" in _decode(output)["hookSpecificOutput"]["additionalContext"].lower()


def test_stop_blocks_unverified_active_pipeline_once(tmp_path):
    _feature_no_tdd(tmp_path)

    output = handle_payload({"hook_event_name": "Stop"}, harness_home=tmp_path)

    data = _decode(output)
    assert data["decision"] == "block"
    assert "verification" in data["reason"].lower()


def test_stop_keeps_blocking_until_fresh_verification(tmp_path):
    _feature_no_tdd(tmp_path)

    first = _decode(handle_payload({"hook_event_name": "Stop"}, harness_home=tmp_path))
    second = _decode(handle_payload({"hook_event_name": "Stop"}, harness_home=tmp_path))

    assert first["decision"] == second["decision"] == "block"


def test_stop_block_output_uses_codex_stop_schema_only(tmp_path):
    _feature_no_tdd(tmp_path)

    output = handle_payload({"hook_event_name": "Stop"}, harness_home=tmp_path)

    data = _decode(output)
    assert set(data) == {"decision", "reason"}
    assert data["decision"] == "block"
    assert data["reason"].strip()
    assert "hookSpecificOutput" not in data


def test_stop_hook_active_does_not_loop(tmp_path):
    output = handle_payload({"hook_event_name": "Stop", "stop_hook_active": True}, harness_home=tmp_path)

    assert output == ""


def test_extract_exit_code_from_current_nested_tool_response():
    payload = {
        "tool_response": {
            "content": [
                {
                    "type": "text",
                    "text": "Script completed\nProcess exited with code 0\nFinal output:\n75 passed",
                }
            ]
        }
    }

    assert _extract_exit_code(payload) == 0


def test_successful_verification_is_recorded_from_nested_response(tmp_path):
    handle_payload(
        {"hook_event_name": "UserPromptSubmit", "prompt": "Corrija o bug."},
        harness_home=tmp_path,
    )

    output = handle_payload(
        {
            "hook_event_name": "PostToolUse",
            "tool_name": "Bash",
            "tool_input": {"cmd": "python -m pytest -q"},
            "tool_response": {"content": [{"type": "text", "text": "Process exited with code 0\n75 passed"}]},
        },
        harness_home=tmp_path,
    )

    assert output == ""
    assert HarnessStateStore(tmp_path).load()["verified"] is True


def test_verification_detection_requires_an_actual_test_runner_command():
    assert _looks_like_verification("python -m pytest -q") is True
    assert _looks_like_verification("npm run test") is True
    assert _looks_like_verification("echo pytest 1 passed") is False
    assert _looks_like_verification("python -c \"print('pytest 1 passed')\"") is False
    assert _is_shell_tool({"tool_name": "shell_command"}) is True
    assert _is_shell_tool({"tool_name": "exec_command"}) is True
    assert _is_shell_tool({"tool_name": "functions.exec"}) is True


@pytest.mark.parametrize(
    "command",
    [
        "python -m pytest --invalid-option; echo '1 passed'",
        "python -m pytest --invalid-option && echo '1 passed'",
        "python -m pytest --invalid-option || echo '1 passed'",
        "python -m pytest --invalid-option | echo '1 passed'",
        "python -m pytest --invalid-option\necho '1 passed'",
    ],
)
def test_composed_shell_command_is_not_trusted_verification(command):
    assert _looks_like_verification(command) is False


def test_composed_command_cannot_create_automatic_test_evidence(tmp_path):
    handle_payload(
        {"hook_event_name": "UserPromptSubmit", "prompt": "Corrija o bug."},
        harness_home=tmp_path,
    )

    handle_payload(
        {
            "hook_event_name": "PostToolUse",
            "tool_name": "Bash",
            "tool_input": {"cmd": "python -m pytest --invalid-option; echo '1 passed'"},
            "tool_response": {"content": [{"type": "text", "text": "Process exited with code 0\n1 passed"}]},
        },
        harness_home=tmp_path,
    )

    assert HarnessStateStore(tmp_path).load()["verified"] is False


def test_shell_command_invalidates_prior_evidence_without_promoting_file_count(tmp_path):
    store = HarnessStateStore(tmp_path)
    handle_payload(
        {"hook_event_name": "UserPromptSubmit", "prompt": "Corrija o bug."},
        harness_home=tmp_path,
    )
    store.mark_verified("python -m pytest -q")
    before = store.load()

    handle_payload(
        {
            "hook_event_name": "PostToolUse",
            "tool_name": "shell_command",
            "tool_input": {"cmd": "sed -i s/old/new/ app.py"},
            "tool_response": {"exit_code": 0, "output": ""},
        },
        harness_home=tmp_path,
    )

    after = store.load()
    assert after["verified"] is False
    assert after["code_revision"] == before["code_revision"] + 1
    assert after["files"] == before["files"]


def test_zero_collected_tests_do_not_satisfy_stop_gate(tmp_path):
    handle_payload(
        {"hook_event_name": "UserPromptSubmit", "prompt": "Corrija o bug."},
        harness_home=tmp_path,
    )

    handle_payload(
        {
            "hook_event_name": "PostToolUse",
            "tool_name": "Bash",
            "tool_input": {"cmd": "python -m pytest -q"},
            "tool_response": {"content": [{"type": "text", "text": "Process exited with code 0\nno tests ran"}]},
        },
        harness_home=tmp_path,
    )

    assert HarnessStateStore(tmp_path).load()["verified"] is False
    assert _decode(handle_payload({"hook_event_name": "Stop"}, harness_home=tmp_path))["decision"] == "block"


def _feature_em_tdd_constatado(home) -> None:
    """Como `_feature_no_tdd`, mas constata cada efeito do hook antes de usa-lo.

    Usado so pela sonda de escalada: se o hook nao criar a task, ou a task nao
    chegar ativa a `tdd`, a reprovacao sai daqui, por assercao, e nao de uma
    guarda da producao chamada mais adiante."""
    from harness4codex.cli import _sync_task_projection

    handle_payload({"hook_event_name": "UserPromptSubmit", "prompt": "Implemente exportacao CSV."}, harness_home=home)
    store = HarnessStateStore(home)
    criado = store.load()
    assert criado.get("task_id"), f"o hook nao criou task pelo UserPromptSubmit: {criado!r}"
    assert criado.get("status") == "active", f"task criada pelo hook nao esta ativa: {criado!r}"
    assert criado.get("kind") == "feature", f"task criada pelo hook nao e feature: {criado!r}"
    assert criado.get("current_step") == "write-spec-light", f"task nao comecou na primeira fase: {criado!r}"

    task_id = criado["task_id"]
    task = store.database.record_artifact(task_id, "spec-light", "docs/specs/csv-spec-light.md", None)
    task = store.database.transition(task_id, "tdd", expected_revision=task["revision"])
    _sync_task_projection(home, task)

    em_tdd = HarnessStateStore(home).load()
    assert em_tdd.get("task_id") == task_id, f"a task ativa mudou ao avancar: {em_tdd!r}"
    assert em_tdd.get("current_step") == "tdd", f"a task nao chegou a tdd: {em_tdd!r}"
    assert em_tdd.get("status") == "active", f"a task em tdd nao esta ativa: {em_tdd!r}"
    assert em_tdd.get("pending_gate") is None, f"portao aberto antes do Stop: {em_tdd!r}"


def test_stop_escalates_after_two_automatic_continuations_then_allows_human_gate(tmp_path):
    _feature_em_tdd_constatado(tmp_path)

    for continuacao in (1, 2):
        saida = handle_payload({"hook_event_name": "Stop"}, harness_home=tmp_path)
        assert saida, f"o Stop {continuacao} nao produziu saida: deveria bloquear a continuacao automatica"
        assert _decode(saida)["decision"] == "block"
        intermediario = HarnessStateStore(tmp_path).load()
        assert intermediario.get("status") == "active", f"Stop {continuacao} tirou a task de ativa: {intermediario!r}"
        assert intermediario.get("pending_gate") is None, f"Stop {continuacao} abriu portao cedo: {intermediario!r}"
    escalation = _decode(handle_payload({"hook_event_name": "Stop"}, harness_home=tmp_path))

    assert escalation["decision"] == "block"
    assert "user" in escalation["reason"].lower()
    state = HarnessStateStore(tmp_path).load()
    assert state["status"] == "awaiting_gate"
    assert state["pending_gate"] == "escalation"
    assert handle_payload({"hook_event_name": "Stop"}, harness_home=tmp_path) == ""


def test_write_after_verification_invalidates_the_gate(tmp_path):
    store = HarnessStateStore(tmp_path)
    handle_payload(
        {"hook_event_name": "UserPromptSubmit", "prompt": "Corrija o bug."},
        harness_home=tmp_path,
    )
    store.mark_verified("python -m pytest -q")

    handle_payload(
        {
            "hook_event_name": "PostToolUse",
            "tool_name": "apply_patch",
            "tool_input": {"patch": "*** Update File: app.py\n"},
        },
        harness_home=tmp_path,
    )

    state = store.load()
    assert state["verified"] is False
    assert state["status"] == "active"


def test_utf8_hook_input_is_decoded_independently_of_windows_stdio():
    payload = _decode_payload('{"hook_event_name":"UserPromptSubmit","prompt":"correção e ciência"}'.encode())

    assert payload["prompt"] == "correção e ciência"


def test_session_history_is_recorded_in_the_shared_memory_store(tmp_path):
    handle_payload(
        {
            "hook_event_name": "UserPromptSubmit",
            "session_id": "session-a",
            "cwd": str(tmp_path),
            "prompt": "Corrija o bug de autenticação.",
        },
        harness_home=tmp_path,
    )

    assert HarnessMemoryStore(tmp_path).history_count() == 1


def test_science_evidence_intent_is_added_to_prompt_context(tmp_path):
    output = handle_payload(
        {
            "hook_event_name": "UserPromptSubmit",
            "prompt": "Analise as evidências científicas e claims do corpus.",
        },
        harness_home=tmp_path,
    )

    context = _decode(output)["hookSpecificOutput"]["additionalContext"]
    assert "science_harness" in context
    assert "read-only" in context


def _lite_preview_events(home) -> list[dict]:
    path = HarnessStateStore(home).events_path
    if not path.exists():
        return []
    records = [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]
    return [record for record in records if record["event"] == "HarnessLitePreview"]


def _count_lite_http(monkeypatch) -> list[str]:
    from harness4codex.harness_lite_adapter import HarnessLiteClient, LiteCallResult

    calls: list[str] = []

    def fake_post(self, path, body):
        calls.append(path)
        return LiteCallResult(True, 200, result={"eligible": True, "riskTier": "R2", "runner": "x", "modelAlias": "m"})

    monkeypatch.setattr(HarnessLiteClient, "_post", fake_post)
    return calls


def _lite_prompt(tmp_path) -> dict:
    # tmp_path nao e repositorio git; o cwd do proprio repo garante o base_revision da previa.
    from pathlib import Path

    return {
        "hook_event_name": "UserPromptSubmit",
        "prompt": "Implemente exportacao CSV.",
        "cwd": str(Path(__file__).resolve().parents[1]),
    }


def test_lite_preview_off_by_default_makes_no_http_call_and_no_event(tmp_path, monkeypatch):
    # HARNESS_CONTROL_TOKEN presente (como nas variaveis de usuario): so o interruptor decide.
    monkeypatch.setenv("HARNESS_CONTROL_TOKEN", "lite-token")
    monkeypatch.delenv("HARNESS4CODEX_LITE_PREVIEW", raising=False)
    calls = _count_lite_http(monkeypatch)

    output = handle_payload(_lite_prompt(tmp_path), harness_home=tmp_path)

    assert calls == []
    assert _lite_preview_events(tmp_path) == []
    assert "HARNESS LITE" not in _decode(output)["hookSpecificOutput"]["additionalContext"]


def test_lite_preview_on_with_token_calls_the_plane_as_before(tmp_path, monkeypatch):
    monkeypatch.setenv("HARNESS_CONTROL_TOKEN", "lite-token")
    monkeypatch.setenv("HARNESS4CODEX_LITE_PREVIEW", "true")
    calls = _count_lite_http(monkeypatch)

    output = handle_payload(_lite_prompt(tmp_path), harness_home=tmp_path)

    assert calls == ["/control/v1/routes/preview"]
    assert [event["payload"]["ok"] for event in _lite_preview_events(tmp_path)] == [True]
    assert "HARNESS LITE preview (advisory)" in _decode(output)["hookSpecificOutput"]["additionalContext"]


# SubagentStart sem contrato de no. Ate 1adb380 o hook mandava todo subagente
# "return role, status, findings, evidence_refs, coverage, and errors", contra o
# `NodeResult` que `skills/codex-harness-workflow/SKILL.md` exige dos nos do censo
# (`node_id, status, summary, artifacts, evidence, risks, questions`). A L-64
# (master-harness `docs/CONTEXT.md`) poe o contrato na skill; o hook chega a todo
# subagente, no de censo ou nao, e nao tem como saber qual contrato vale para ele.
# Mesmo conserto do harness4claude em 2026-09-30
# (`docs/specs/subagent-start-resuming-diagnostico.md`): registrar e nao emitir.
SUBAGENT_START_OLD_REF = "1adb380"
AGENT_TYPES = ["worker", "explorer", "default", None]


def _subagent_start(handler, home, agent_type) -> str:
    """Task viva aberta pelo prompt e um SubagentStart, pela funcao de producao passada."""
    handler({"hook_event_name": "UserPromptSubmit", "prompt": "Implemente exportacao CSV."}, harness_home=home)
    payload = {"hook_event_name": "SubagentStart", "agent_id": "agent-1"}
    if agent_type is not None:
        payload["agent_type"] = agent_type
    return handler(payload, harness_home=home)


def _subagent_events(home) -> list[dict]:
    path = HarnessStateStore(home).events_path
    records = [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]
    return [record for record in records if record["event"] == "SubagentStart"]


@pytest.mark.parametrize("agent_type", AGENT_TYPES)
def test_subagent_start_registra_e_nao_emite(tmp_path, agent_type):
    output = _subagent_start(handle_payload, tmp_path, agent_type)

    assert output == ""
    assert [event["payload"] for event in _subagent_events(tmp_path)] == [
        {"agent_id": "agent-1", "agent_type": agent_type}
    ]


def _hook_at(ref: str):
    """Carrega `harness4codex/hook.py` de `ref` como modulo irmao do pacote atual."""
    import importlib.util
    import subprocess
    from pathlib import Path

    repo = Path(__file__).resolve().parents[1]
    source = subprocess.run(
        ["git", "show", f"{ref}:harness4codex/hook.py"],
        cwd=repo,
        capture_output=True,
        text=True,
        encoding="utf-8",
        timeout=60,
        check=True,
    ).stdout
    spec = importlib.util.spec_from_loader(f"harness4codex._hook_{ref}", loader=None)
    module = importlib.util.module_from_spec(spec)
    module.__package__ = "harness4codex"
    exec(compile(source, f"{ref}:harness4codex/hook.py", "exec"), module.__dict__)
    return module


def test_CONTROLE_hook_antigo_mandava_subagente_seguir_outro_contrato(tmp_path):
    """Metade de falsificacao: o mesmo cenario, contra o hook fixado por SHA, ve a linha."""
    old = _hook_at(SUBAGENT_START_OLD_REF)

    output = _subagent_start(old.handle_payload, tmp_path, "worker")

    context = _decode(output)["hookSpecificOutput"]["additionalContext"]
    assert "node contract" in context
    assert "evidence_refs" in context
