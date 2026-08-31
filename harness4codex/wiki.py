from __future__ import annotations

import hashlib
import re
import sqlite3
from pathlib import Path
from typing import Any


class WikiIndex:
    def __init__(self, root: str | Path, database: str | Path | None = None):
        self.root = Path(root).resolve()
        self.database = Path(database) if database else self.root / ".harness4codex" / "wiki.db"

    def rebuild(self) -> dict[str, int]:
        if not self.root.exists():
            return {"pages": 0, "sections": 0}
        self.database.parent.mkdir(parents=True, exist_ok=True)
        pages = sections = 0
        with sqlite3.connect(self.database) as connection:
            connection.executescript(
                """
                CREATE TABLE IF NOT EXISTS wiki_sections(
                    id INTEGER PRIMARY KEY,
                    page TEXT NOT NULL,
                    section TEXT NOT NULL,
                    text TEXT NOT NULL,
                    content_hash TEXT NOT NULL
                );
                CREATE VIRTUAL TABLE IF NOT EXISTS wiki_fts USING fts5(
                    page, section, text, content='wiki_sections', content_rowid='id'
                );
                DELETE FROM wiki_sections;
                DELETE FROM wiki_fts;
                """
            )
            for path in sorted(self.root.rglob("*.md")):
                if ".harness4codex" in path.parts:
                    continue
                relative = path.relative_to(self.root).as_posix()
                page_sections = _sections(path.read_text(encoding="utf-8"))
                pages += 1
                for heading, text in page_sections:
                    cursor = connection.execute(
                        "INSERT INTO wiki_sections(page, section, text, content_hash) VALUES (?, ?, ?, ?)",
                        (relative, heading, text, hashlib.sha256(text.encode("utf-8")).hexdigest()),
                    )
                    connection.execute(
                        "INSERT INTO wiki_fts(rowid, page, section, text) VALUES (?, ?, ?, ?)",
                        (cursor.lastrowid, relative, heading, text),
                    )
                    sections += 1
        return {"pages": pages, "sections": sections}

    def query(self, question: str, *, top_k: int = 5) -> dict[str, Any]:
        if not self.root.exists() or not self.database.exists():
            return {"available": False, "confident_hits": 0, "hits": []}
        tokens = re.findall(r"[\w-]+", question.casefold(), flags=re.UNICODE)
        if not tokens:
            return {"available": True, "confident_hits": 0, "hits": []}
        expression = " OR ".join(f'"{token}"' for token in tokens)
        with sqlite3.connect(self.database) as connection:
            connection.row_factory = sqlite3.Row
            rows = connection.execute(
                """
                SELECT wiki_sections.page, wiki_sections.section, wiki_sections.text,
                       bm25(wiki_fts) AS rank
                FROM wiki_fts JOIN wiki_sections ON wiki_sections.id = wiki_fts.rowid
                WHERE wiki_fts MATCH ? ORDER BY rank LIMIT ?
                """,
                (expression, max(int(top_k), 1)),
            ).fetchall()
        hits = []
        query_tokens = set(tokens)
        for row in rows:
            text_tokens = set(re.findall(r"[\w-]+", str(row["text"]).casefold(), flags=re.UNICODE))
            coverage = len(query_tokens & text_tokens) / len(query_tokens)
            relative = Path(str(row["page"])).with_suffix("").as_posix()
            hits.append(
                {
                    "page": row["page"],
                    "wikilink": f"[[{relative}]]",
                    "section": row["section"],
                    "text": row["text"],
                    "score": coverage,
                    "confident": coverage >= 0.45,
                }
            )
        return {
            "available": True,
            "confident_hits": sum(1 for hit in hits if hit["confident"]),
            "hits": hits,
        }


def _sections(text: str) -> list[tuple[str, str]]:
    current = "Document"
    buffer: list[str] = []
    result: list[tuple[str, str]] = []
    for line in text.splitlines():
        match = re.match(r"^#{1,6}\s+(.+)$", line)
        if match:
            if any(value.strip() for value in buffer):
                result.append((current, "\n".join(buffer).strip()))
            current = match.group(1).strip()
            buffer = []
        else:
            buffer.append(line)
    if any(value.strip() for value in buffer):
        result.append((current, "\n".join(buffer).strip()))
    return result or [(current, text.strip())]
