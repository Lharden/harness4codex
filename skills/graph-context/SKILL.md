---
name: graph-context
description: Use in Harness4Codex L2 work and codebase questions to obtain scoped structural context from Graphify before raw file exploration.
---

# Graph Context for Harness4Codex

If `graphify-out/graph.json` exists, read `GRAPH_REPORT.md`, check freshness against
Git HEAD and source mtimes, then run a focused `graphify query`, `path`, or `explain`.
Summarize only task-relevant god nodes, communities, dependencies and confidence.
Record source graph hash, freshness and query in a graph-context artifact.

If the graph is stale, run `graphify update .` when Graphify is already available;
otherwise label structural claims unobserved. If no graph exists, use bounded `rg` and
file inspection. Absence of Graphify degrades capability but never stalls the pipeline.
After code changes, update an existing graph and keep `graphify-out/` ignored.
