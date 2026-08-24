from harness4codex.science_adapter import science_context, wants_science_evidence


def test_scientific_evidence_prompts_activate_the_read_only_mcp_route():
    prompt = "Compare as evidências científicas e encontre claims no corpus."

    assert wants_science_evidence(prompt) is True
    context = science_context(prompt)
    assert "science_harness" in context
    assert "search_claims" in context
    assert "get_claim" in context
    assert "read-only" in context


def test_ordinary_bugfix_does_not_activate_science_route():
    assert wants_science_evidence("Corrija o bug do login.") is False
    assert science_context("Corrija o bug do login.") == ""
