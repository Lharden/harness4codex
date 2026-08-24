import pytest

import harness4codex.harness_lite_adapter as adapter
from harness4codex.harness_lite_adapter import (
    HarnessLiteClient,
    build_task_envelope,
    evidence_bundle_is_acceptable,
    execution_is_enabled,
    lite_route_for,
    project_fingerprint_for,
    reaches_the_plane,
)


def test_c0_stays_local_and_all_work_levels_can_be_previewed():
    assert reaches_the_plane("C0") is False
    for level in ("C1", "C2", "C3", "CR", "DOCS"):
        assert reaches_the_plane(level) is True


def test_obsolete_supervisor_wire_projection_is_not_exported():
    assert not hasattr(adapter, "to_wire")
    assert not hasattr(adapter, "build_supervisor_request")


def test_codex_levels_map_to_the_lite_contract_without_leaking_codex_levels():
    assert lite_route_for("C0") == ("L0", "R0", "diagnose", "read-only")
    assert lite_route_for("C1") == ("L1", "R1", "diagnose", "isolated-worktree")
    assert lite_route_for("C2") == ("L2", "R2", "implement", "isolated-worktree")
    assert lite_route_for("C3") == ("L2", "R3", "implement", "isolated-worktree")
    assert lite_route_for("CR") == ("L1", "R1", "review", "read-only")
    assert lite_route_for("DOCS") == ("L1", "R0", "verify", "read-only")


def test_preview_envelope_matches_harness_lite_task_envelope_v1():
    envelope = build_task_envelope(
        level="C2",
        objective="Implementar exportação CSV",
        workspace_path=r"C:\repo",
        base_revision="a" * 40,
        session_id="S-1",
    )

    assert set(envelope) == {
        "schemaVersion",
        "kind",
        "objective",
        "workspace",
        "inputs",
        "acceptance",
        "execution",
        "provenance",
    }
    assert envelope["schemaVersion"] == "1"
    assert envelope["execution"]["riskHint"] == "R2"
    assert envelope["execution"]["mutation"] == "isolated-worktree"
    assert envelope["execution"]["allowedWriteGlobs"] == ["**"]
    assert envelope["acceptance"]["criteria"]
    assert "level" not in envelope
    assert "stage" not in envelope


def test_read_only_envelope_declares_no_write_globs():
    envelope = build_task_envelope(
        level="CR",
        objective="Revisar mudança",
        workspace_path=r"C:\repo",
        base_revision="b" * 40,
        session_id="S-2",
    )

    assert envelope["execution"]["mutation"] == "read-only"
    assert envelope["execution"]["allowedWriteGlobs"] == []


def test_same_envelope_inputs_produce_same_idempotency_key():
    arguments = {
        "level": "C2",
        "objective": "Implementar CSV",
        "workspace_path": r"C:\repo",
        "base_revision": "d" * 40,
        "session_id": "S-4",
    }

    assert build_task_envelope(**arguments)["provenance"] == build_task_envelope(**arguments)["provenance"]


def test_lite_client_posts_authenticated_preview_without_putting_token_in_body():
    seen = {}

    class Response:
        status = 200

        def __enter__(self):
            return self

        def __exit__(self, *_args):
            return False

        def read(self):
            return b'{"ok":true,"result":{"eligible":true,"riskTier":"R2"}}'

    def opener(request, timeout):
        seen["url"] = request.full_url
        seen["authorization"] = request.headers["Authorization"]
        seen["body"] = request.data.decode("utf-8")
        seen["timeout"] = timeout
        return Response()

    client = HarnessLiteClient("http://127.0.0.1:8787", "secret-token", opener=opener)
    result = client.preview(
        build_task_envelope(
            level="C2",
            objective="Implementar CSV",
            workspace_path=r"C:\repo",
            base_revision="c" * 40,
            session_id="S-3",
        )
    )

    assert result.ok is True
    assert seen["url"].endswith("/control/v1/routes/preview")
    assert seen["authorization"] == "Bearer secret-token"
    assert "secret-token" not in seen["body"]
    assert seen["timeout"] <= 2.0


def test_lite_client_refuses_to_send_the_control_token_off_loopback():
    with pytest.raises(ValueError, match="loopback"):
        HarnessLiteClient("https://example.com", "secret-token")


def test_lite_execution_requires_explicit_enable_and_positive_budget():
    assert execution_is_enabled({}) is False
    assert execution_is_enabled({"HARNESS4CODEX_LITE_EXECUTE": "true"}) is False
    assert execution_is_enabled(
        {"HARNESS4CODEX_LITE_EXECUTE": "true", "HARNESS4CODEX_LITE_MAX_COST_USD": "1.50"}
    ) is True


def test_evidence_bundle_requires_success_artifacts_and_criterion_evidence():
    bundle = {
        "status": "succeeded",
        "artifacts": [{"uri": "file:///result"}],
        "acceptance": [{"criterionId": "AC-1", "outcome": "pass", "evidence": [{"uri": "file:///proof"}]}],
    }

    assert evidence_bundle_is_acceptable(bundle) is True
    assert evidence_bundle_is_acceptable({**bundle, "artifacts": []}) is False
    assert evidence_bundle_is_acceptable({**bundle, "status": "failed"}) is False
    assert evidence_bundle_is_acceptable({**bundle, "acceptance": [{"outcome": "pass", "evidence": []}]}) is False


def test_project_fingerprint_is_order_independent():
    assert project_fingerprint_for(["b", "a"]) == project_fingerprint_for(["a", "b"])
    assert project_fingerprint_for(["a"]) != project_fingerprint_for(["a", "b"])
