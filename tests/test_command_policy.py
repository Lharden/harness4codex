from harness4codex.command_policy import evaluate_command, parse_invocations


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


def test_call_operator_and_wrappers_do_not_hide_the_program():
    """2026-10-14: o programa era sempre o primeiro token. `& git push --force` rodou numa sessao real do
    Codex com o hook ligado, lido como o programa `&` (master-harness, plano-desktop §13.26)."""
    assert evaluate_command("& git push --force").action == "deny"
    assert evaluate_command('& "C:/Program Files/Git/cmd/git.exe" push --force').action == "deny"
    assert evaluate_command(". git reset --hard").action == "deny"
    assert evaluate_command("GIT_TRACE=1 git push --force").action == "deny"
    assert evaluate_command("env GIT_TRACE=1 git clean -fd").action == "deny"
    assert evaluate_command("command git push -f").action == "deny"
    assert evaluate_command("nohup git push --force").action == "deny"
    assert evaluate_command("time git reset --hard").action == "deny"


def test_call_operator_and_wrappers_keep_benign_commands_allowed():
    assert evaluate_command("& git status").action == "allow"
    assert evaluate_command(". ./setup.ps1").action == "allow"
    assert evaluate_command("env").action == "allow"
    assert evaluate_command("GIT_TRACE=1 git status").action == "allow"
    assert evaluate_command("command -v git").action == "allow"


def test_single_ampersand_separates_commands():
    """`&` sozinho e o operador de segundo plano do bash e do PowerShell 7: o que vem depois e outro comando."""
    assert evaluate_command("sleep 1 & git push --force").action == "deny"
    assert evaluate_command("git status & git reset --hard").action == "deny"


def test_ampersand_in_redirection_is_not_a_separator():
    """Cortar o `2>&1` nao muda a decisao, so cria um trecho falso; por isso o teste olha as invocacoes."""
    for command in ("git status 2>&1", "git status &> saida.txt", "git status >&2", "git status <&3"):
        assert [i.program for i in parse_invocations(command)] == ["git"], command
    assert evaluate_command("git push --force 2>&1").action == "deny"


def test_sh_family_script_is_found_after_combined_or_separate_flags():
    """2026-10-14: so `-c` exato como primeiro argumento abria o script; `bash -lc '...'` passava."""
    assert evaluate_command("bash -lc 'git push --force'").action == "deny"
    assert evaluate_command("bash -l -c 'git reset --hard'").action == "deny"
    assert evaluate_command('sh -ec "git clean -fd"').action == "deny"
    assert evaluate_command("bash -o pipefail -c 'git push -f'").action == "deny"
    assert evaluate_command("zsh -c 'git push --force'").action == "deny"


def test_sh_family_benign_scripts_and_files_still_allow():
    assert evaluate_command("bash -lc 'git status'").action == "allow"
    assert evaluate_command("bash script.sh").action == "allow"
    assert evaluate_command("bash --norc script.sh").action == "allow"


def test_cmd_and_powershell_script_is_the_rest_of_the_line():
    """2026-10-14: `cmd /c git push --force` lia so `git` como script. No cmd e no PowerShell, o que vem
    depois de `/c` e de `-Command` e a linha inteira."""
    assert evaluate_command("cmd /c git push --force").action == "deny"
    assert evaluate_command('cmd.exe /s /c "git push --force"').action == "deny"
    assert evaluate_command("cmd /C git reset --hard").action == "deny"
    assert evaluate_command("pwsh -Command git push --force").action == "deny"
    assert evaluate_command("powershell.exe -NoProfile -Command git push -f").action == "deny"


def test_cmd_and_powershell_benign_lines_keep_their_decision():
    assert evaluate_command("cmd /c git status").action == "allow"
    assert evaluate_command("pwsh -Command git status").action == "allow"
    assert evaluate_command('pwsh -NoProfile -Command "git push origin main"').action == "warn"
