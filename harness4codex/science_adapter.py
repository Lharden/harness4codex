from __future__ import annotations

import re
import unicodedata

SCIENCE_PATTERNS = (
    r"\bscience harness\b",
    r"\bscientific\b",
    r"\bcientific[oa]s?\b",
    r"\bevidencias?\b",
    r"\bclaims?\b",
    r"\bcorpus\b",
    r"\bliterature\b",
    r"\bliteratura\b",
    r"\bartigos?\b",
    r"\bpapers?\b",
)


def _normalize(text: str) -> str:
    decomposed = unicodedata.normalize("NFKD", text)
    return decomposed.encode("ascii", "ignore").decode("ascii").lower()


def wants_science_evidence(prompt: str) -> bool:
    normalized = _normalize(prompt)
    return any(re.search(pattern, normalized) for pattern in SCIENCE_PATTERNS)


def science_context(prompt: str) -> str:
    if not wants_science_evidence(prompt):
        return ""
    return (
        "SCIENCE HARNESS (read-only evidence route)\n"
        "Use the `science_harness` MCP server. Call `server_info`/`list_corpora` when discovery is needed, "
        "then `search_claims` and `get_claim`. Cite claim identifiers and preserve corpus provenance."
    )
