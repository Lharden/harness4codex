from harness4codex.git_guard import inspect_command


def test_blocks_force_push():
    decision = inspect_command("git push --force origin main")

    assert decision.blocked is True
    assert "force" in decision.reason.lower()


def test_blocks_reset_hard():
    decision = inspect_command("git reset --hard HEAD~1")

    assert decision.blocked is True
    assert "reset --hard" in decision.reason.lower()


def test_blocks_clean_force():
    decision = inspect_command("git clean -fd")

    assert decision.blocked is True
    assert "clean" in decision.reason.lower()


def test_normal_push_warns_without_blocking():
    decision = inspect_command("git push origin feature/harness")

    assert decision.blocked is False
    assert decision.warning
    assert "push" in decision.warning.lower()


def test_safe_command_allowed():
    decision = inspect_command("python -m pytest tests -q")

    assert decision.blocked is False
    assert decision.warning is None
