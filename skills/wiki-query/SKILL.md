---
name: wiki-query
description: Use when Harness4Codex needs prior decisions, assimilated techniques or work history from the AI-Brain wiki with citations.
---

# Wiki Query for Harness4Codex

Resolve the vault root from `AI_BRAIN_PATH` or `<VAULT_PATH>/AI-Brain`. Refresh a stale
index, then query through `harness4codex wiki query "<question>" --top-k 5`.
Ranking selects candidates; read the pages before judging relevance. Cite every wiki
claim as `[[path/page]]` and label low-confidence or unavailable coverage.

Use Graphify for current code structure and the wiki for why a decision exists. Query
is read-only. A genuinely new positive discovery may be proposed as a page; rejected
editorial directions do not become thematic memory.
