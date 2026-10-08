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


def test_git_global_options_do_not_hide_the_subcommand():
    """2026-10-07: `-C <dir>` era lido como subcomando, e 12 `branch -D` reais
    passaram como allow nos transcripts da maquina (lado harness4claude)."""
    assert evaluate_command("git -C repo reset --hard").action == "deny"
    assert evaluate_command('git -C "$M" branch -D tmp/x').action == "deny"
    assert evaluate_command("git --no-pager push --force").action == "deny"
    assert evaluate_command("git -c core.x=y clean -fd").action == "deny"
    assert evaluate_command("git --git-dir=/r/.git --work-tree /r restore .").action == "deny"
    assert evaluate_command("git -C repo push origin main").action == "warn"


def test_git_global_options_alone_or_benign_still_allow():
    assert evaluate_command("git --version").action == "allow"
    assert evaluate_command("git -C repo status").action == "allow"
    assert evaluate_command("git -C repo branch -d merged").action == "allow"
    assert evaluate_command("git -c user.name=x commit -m msg").action == "allow"
