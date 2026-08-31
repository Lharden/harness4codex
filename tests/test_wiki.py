from pathlib import Path

from harness4codex.wiki import WikiIndex


def test_wiki_index_returns_cited_sections_and_confidence(tmp_path: Path):
    root = tmp_path / "AI-Brain"
    page = root / "wiki" / "decisions" / "state.md"
    page.parent.mkdir(parents=True)
    page.write_text("# Durable state\n\nSQLite WAL protects transactional pipeline state.\n", encoding="utf-8")
    index = WikiIndex(root)
    index.rebuild()

    result = index.query("transactional SQLite state", top_k=3)

    assert result["available"] is True
    assert result["hits"][0]["wikilink"] == "[[wiki/decisions/state]]"
    assert "SQLite WAL" in result["hits"][0]["text"]
    assert result["hits"][0]["confident"] is True


def test_wiki_query_degrades_when_vault_is_missing(tmp_path: Path):
    result = WikiIndex(tmp_path / "missing").query("anything")

    assert result == {"available": False, "confident_hits": 0, "hits": []}
