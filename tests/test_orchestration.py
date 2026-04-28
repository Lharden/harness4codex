import json

from harness4codex.orchestration import Issue, OrchestrationPolicy, WorkspaceManager


def test_workspace_manager_creates_deterministic_issue_workspace(tmp_path):
    issue = Issue(id="issue-1", identifier="ABC-123", title="Fix login")

    workspace = WorkspaceManager(tmp_path).prepare(issue)

    assert workspace.path.name == "ABC-123"
    assert workspace.created_now is True
    metadata = json.loads((workspace.path / ".harness4codex-issue.json").read_text(encoding="utf-8"))
    assert metadata["issue"]["identifier"] == "ABC-123"


def test_workspace_manager_sanitizes_identifier(tmp_path):
    issue = Issue(id="issue-1", identifier="../ABC 123", title="Fix login")

    workspace = WorkspaceManager(tmp_path).prepare(issue)

    assert workspace.path.name == "ABC-123"
    assert workspace.path.parent == tmp_path


def test_policy_blocks_issue_with_active_blocker():
    policy = OrchestrationPolicy(active_states=["Ready"], terminal_states=["Done"])
    issue = Issue(
        id="issue-2",
        identifier="ABC-2",
        title="Feature",
        state="Ready",
        blocked_by=[{"identifier": "ABC-1", "state": "In Progress"}],
    )

    assert policy.is_eligible(issue) is False


def test_policy_allows_issue_when_blockers_terminal():
    policy = OrchestrationPolicy(active_states=["Ready"], terminal_states=["Done"])
    issue = Issue(
        id="issue-2",
        identifier="ABC-2",
        title="Feature",
        state="Ready",
        blocked_by=[{"identifier": "ABC-1", "state": "Done"}],
    )

    assert policy.is_eligible(issue) is True


def test_retry_backoff_is_exponential_and_capped():
    policy = OrchestrationPolicy(max_retry_backoff_ms=10_000)

    assert policy.retry_backoff_ms(0) == 1_000
    assert policy.retry_backoff_ms(3) == 8_000
    assert policy.retry_backoff_ms(20) == 10_000
