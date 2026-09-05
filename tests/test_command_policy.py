from harness4codex.command_policy import evaluate_command


def test_quoted_git_text_is_not_treated_as_execution():
    decision = evaluate_command("python -c \"print('git reset --hard')\"")

    assert decision.action == "allow"


def test_destructive_command_in_chain_is_denied():
    decision = evaluate_command("echo ready && git clean -fd")

    assert decision.action == "deny"
    assert decision.invocation.program == "git"


def test_force_push_and_hard_reset_are_denied():
    assert evaluate_command("git push origin main --force-with-lease").action == "deny"
    assert evaluate_command("git reset --hard HEAD~1").action == "deny"


def test_external_plugin_mutation_requires_approval():
    decision = evaluate_command("codex plugin add example")

    assert decision.action == "require_approval"
    assert decision.invocation.program == "codex"


def test_plain_push_warns_and_parser_failure_is_observable():
    assert evaluate_command("git push origin feature").action == "warn"
    assert evaluate_command("git 'unterminated").action == "unknown"
