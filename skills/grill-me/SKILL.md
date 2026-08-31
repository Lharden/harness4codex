---
name: grill-me
description: Use after a Harness4Codex L2 specification to run independent adversarial reviews and produce a reconciled risk ledger.
---

# Grill Me for Harness4Codex

Review the spec through five independent lenses: requirements ambiguity, failure and
recovery, security/privacy, operability/performance, and testability/migration.

When agent delegation is authorized, publish a node census and dispatch one clean
context per lens. Give reviewers the spec and evidence, not producer rationale. Require
the `NodeResult` contract. Reconcile returns into a table with finding id, severity,
evidence, affected REQ/AC, decision and owner. Inspect actual artifacts and shared diff.

If delegation is unavailable, execute the five lenses sequentially and label their
independence limitation. Resolve concrete spec gaps before opening `approve-spec`.
Record the review ledger as artifact type `adversarial-review`.
