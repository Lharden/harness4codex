---
name: compress-memory
description: Use when Harness4Codex secondary memory files are large and can be losslessly tightened without touching specifications or core instructions.
---

# Compress Memory for Harness4Codex

Run `harness4codex memory compress <path> --dry-run` first. Eligible files are
secondary operational notes. Protected inputs include specs, design/verification
artifacts, AGENTS.md, MEMORY.md, core memory, manifests and any file containing
Given/When/Then, `[NEEDS CLARIFICATION]` or REQ identifiers.

Preserve frontmatter, headings, code, URLs, paths, commands, flags, tables, lists,
numbers and technical claims. A write creates `<name>.original.md`, is idempotent and
reports byte/line savings. Validate protected-content hashes after compression.
