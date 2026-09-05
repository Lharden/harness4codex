from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass, field

from .contract import ContractSnapshot


@dataclass(frozen=True)
class Classification:
    level: str
    kind: str
    pipeline: list[str] = field(default_factory=list)
    reasons: list[str] = field(default_factory=list)
    is_task_switch: bool = False


_CONTRACT = ContractSnapshot.load()
BUG_PIPELINE = _CONTRACT.pipeline("L1", "bug")
FEATURE_PIPELINE = _CONTRACT.pipeline("L1", "feature")
ARCHITECTURE_PIPELINE = _CONTRACT.pipeline("L2", "architecture")
REVIEW_PIPELINE = _CONTRACT.pipeline("L1", "review")
DOCS_PIPELINE = _CONTRACT.pipeline("L1", "docs")
OPENAI_DOCS_PIPELINE = DOCS_PIPELINE


TASK_SWITCH_PATTERNS = [
    r"\bnova tarefa\b",
    r"\bnovo pedido\b",
    r"\bnew task\b",
    r"\bswitch task\b",
    r"\bcomece outra\b",
    r"\besquece (isso|a anterior)\b",
]

REVIEW_PATTERNS = [
    r"\breview\b",
    r"\bcode review\b",
    r"\brevise\b",
    r"\bpr\b",
    r"\bpull request\b",
]

DOCS_PATTERNS = [
    r"\bapi atual\b",
    r"\bdocs?\b",
    r"\bdocumenta[cç][aã]o\b",
    r"\bvers[aã]o\b",
    r"\bv\d+(?:\.\d+)?\b",
    r"\bconfigure?\b",
]

DOCS_LIBRARIES = [
    "openai",
    "codex",
    "fastapi",
    "pydantic",
    "react",
    "next",
    "nextjs",
    "vite",
    "django",
    "flask",
    "pytest",
    "playwright",
    "langchain",
    "sqlalchemy",
    "stripe",
    "github",
]

BUG_PATTERNS = [
    r"\bbug\b",
    r"\berro\b",
    r"\bcrash\b",
    r"\bquebra\b",
    r"\bfalha\b",
    r"\bfailing\b",
    r"\bfix\b",
    r"\bcorrij[aoe]\b",
    r"\bdebug\b",
]

ARCHITECTURE_PATTERNS = [
    r"\barquitetura\b",
    r"\barchitecture\b",
    r"\brefator(e|ar|acao|a[cç][aã]o)\b",
    r"\bmigra[cç][aã]o\b",
    r"\bmigrate\b",
    r"\bredesign\b",
    r"\bmodulariz",
    r"\btodos os servicos\b",
    r"\bcross[- ]?module\b",
    r"\bsistema inteiro\b",
]

FEATURE_PATTERNS = [
    r"\bimplemente?\b",
    r"\badicione?\b",
    r"\bcrie?\b",
    r"\bbuild\b",
    r"\bsuporte\b",
    r"\bendpoint\b",
    r"\bexporta[cç][aã]o\b",
    r"\bfeature\b",
    r"\bintegre?\b",
]


def _normalize(prompt: str) -> str:
    normalized = unicodedata.normalize("NFKD", prompt)
    ascii_text = normalized.encode("ascii", "ignore").decode("ascii")
    return ascii_text.lower()


def _matches(patterns: list[str], text: str) -> list[str]:
    return [pattern for pattern in patterns if re.search(pattern, text)]


def classify_prompt(prompt: str) -> Classification:
    text = _normalize(prompt)
    reasons: list[str] = []
    is_task_switch = bool(_matches(TASK_SWITCH_PATTERNS, text))
    if is_task_switch:
        reasons.append("task switch marker")

    review_hits = _matches(REVIEW_PATTERNS, text)
    if review_hits and not _matches(FEATURE_PATTERNS + BUG_PATTERNS, text):
        return Classification("CR", "review", REVIEW_PIPELINE.copy(), review_hits + reasons, is_task_switch)

    docs_hits = _matches(DOCS_PATTERNS, text)
    docs_lib_hits = [library for library in DOCS_LIBRARIES if re.search(rf"\b{re.escape(library)}\b", text)]
    if docs_hits and docs_lib_hits:
        pipeline = OPENAI_DOCS_PIPELINE if {"openai", "codex"}.intersection(docs_lib_hits) else DOCS_PIPELINE
        return Classification("DOCS", "api-docs", pipeline.copy(), docs_hits + docs_lib_hits + reasons, is_task_switch)

    architecture_hits = _matches(ARCHITECTURE_PATTERNS, text)
    if architecture_hits:
        return Classification(
            "C3", "architecture", ARCHITECTURE_PIPELINE.copy(), architecture_hits + reasons, is_task_switch
        )

    bug_hits = _matches(BUG_PATTERNS, text)
    if bug_hits:
        return Classification("C1", "bug", BUG_PIPELINE.copy(), bug_hits + reasons, is_task_switch)

    feature_hits = _matches(FEATURE_PATTERNS, text)
    if feature_hits:
        return Classification("C2", "feature", FEATURE_PIPELINE.copy(), feature_hits + reasons, is_task_switch)

    return Classification("C0", "question", [], ["no implementation signal", *reasons], is_task_switch)
