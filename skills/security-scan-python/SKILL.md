---
name: security-scan-python
description: Use when Harness4Codex is asked to audit Python security or changes touch untrusted input, subprocess, SQL, deserialization, crypto or secrets.
---

# Security Scan Python for Harness4Codex

Check availability before execution. Run Bandit at medium-or-higher severity and
confidence over production Python, excluding VCS, environments, dependencies and test
fixtures. Run `pip-audit` against the project lock or requirements when present.

Report each relevant rule, file:line, severity/confidence, risk and concrete repair.
Justified false positives use a narrow rule-specific suppression. Record command,
versions, exit code and output hash as evidence; a missing scanner is UNOBSERVED, not a
clean result. Installation requires normal user approval.
