from harness4codex.diagnostics import run_doctor


def _write_config(home, text):
    home.mkdir(parents=True, exist_ok=True)
    (home / "config.toml").write_text(text, encoding="utf-8")


def test_doctor_detects_competing_supervisor_and_disabled_required_apps(tmp_path):
    _write_config(
        tmp_path,
        """
[features]
hooks = true
enable_mcp_apps = false

[plugins."harness4codex@personal"]
enabled = true

[plugins."harness4claude@harness4claude"]
enabled = true
""",
    )

    report = run_doctor(tmp_path, env={}, which=lambda _name: None, user_env={})

    assert report.ok is False
    codes = {check.code for check in report.checks if check.status == "fail"}
    assert "MULTIPLE_SUPERVISORS" in codes
    assert "CODEX_APPS_REQUIRED" in codes


def test_doctor_accepts_one_supervisor_obsidian_and_science_mcp(tmp_path):
    _write_config(
        tmp_path,
        """
[features]
hooks = true
enable_mcp_apps = true

[plugins."harness4codex@personal"]
enabled = true

[plugins."harness4claude@harness4claude"]
enabled = false

[mcp_servers.obsidian]
url = "https://127.0.0.1:27124/mcp/"
bearer_token_env_var = "OBSIDIAN_API_KEY"

[mcp_servers.science_harness]
command = "shs"
args = ["claims-mcp"]
""",
    )

    report = run_doctor(
        tmp_path,
        env={"OBSIDIAN_API_KEY": "secret", "HARNESS_CONTROL_TOKEN": "lite-token"},
        which=lambda name: r"C:\bin\shs.exe" if name == "shs" else None,
        user_env={},
    )

    assert report.ok is True
    assert not [check for check in report.checks if check.status == "fail"]
    codes = {check.code for check in report.checks}
    assert "CONTRACT_LOCK_VALID" in codes
    assert "FULL_LIFECYCLE_HOOKS" in codes


def test_doctor_marks_obsidian_restart_when_user_env_has_token_but_process_does_not(tmp_path):
    _write_config(
        tmp_path,
        """
[features]
hooks = true
enable_mcp_apps = true
[plugins."harness4codex@personal"]
enabled = true
[mcp_servers.obsidian]
url = "https://127.0.0.1:27124/mcp/"
bearer_token_env_var = "OBSIDIAN_API_KEY"
[mcp_servers.science_harness]
command = "shs"
args = ["claims-mcp"]
""",
    )

    report = run_doctor(
        tmp_path,
        env={},
        which=lambda name: r"C:\bin\shs.exe" if name == "shs" else None,
        user_env={"OBSIDIAN_API_KEY": "secret", "HARNESS_CONTROL_TOKEN": "lite-token"},
    )

    check = next(item for item in report.checks if item.code == "OBSIDIAN_RESTART_REQUIRED")
    assert check.status == "warn"
    lite = next(item for item in report.checks if item.code == "HARNESS_LITE_RESTART_REQUIRED")
    assert lite.status == "warn"
