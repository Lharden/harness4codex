---
name: verify-against-spec
description: Use at the end of Harness4Codex L1/L2 work to verify every requirement and acceptance criterion with fresh concrete evidence.
---

# Verify Against Spec for Harness4Codex

Create `docs/specs/{slug}-verification.md` from the template.

1. Fail fast when unresolved `[NEEDS CLARIFICATION]` exists.
2. Map every REQ to implementation evidence and every AC to a named test. Use three
   states: COVERED, ORPHANED, UNOBSERVED; unobserved evidence cannot become silent pass.
3. Audit each active assumption against current reality. A false assumption includes
   its REQ/AC/test/file blast radius; rework remains a user decision.
4. Verify new tests demonstrated red before green. Freshly run commands must report a
   nonzero collected count and be recorded with output hash.
5. Inspect `git status --short` and `git diff`; agent reports are claims until matched
   to artifacts. Compare changed paths to governing design `applies_to` patterns.
6. Check boundaries, success metrics, security scans where relevant and claims made by
   documentation.
7. Emit PASS, PARTIAL or FAIL with reason and record artifact type `verification`.

Use `harness4codex evidence record` for machine evidence and `task complete` only after
the current code revision is verified.
