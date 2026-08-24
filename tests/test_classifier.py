from harness4codex.classifier import classify_prompt


def test_simple_question_is_c0():
    result = classify_prompt("Explique rapidamente como este modulo funciona.")

    assert result.level == "C0"
    assert result.kind == "question"
    assert result.pipeline == []


def test_bug_promotes_debugging_and_tdd():
    result = classify_prompt("Corrija este bug: o login quebra quando o token expira.")

    assert result.level == "C1"
    assert result.kind == "bug"
    assert "superpowers:systematic-debugging" in result.pipeline
    assert "superpowers:test-driven-development" in result.pipeline


def test_feature_uses_light_spec_pipeline():
    result = classify_prompt("Implemente exportacao CSV para a tela de relatorios.")

    assert result.level == "C2"
    assert result.kind == "feature"
    assert result.pipeline[0] == "superpowers:brainstorming"
    assert result.pipeline[-1] == "superpowers:verification-before-completion"


def test_architecture_uses_design_and_review():
    result = classify_prompt("Refatore a arquitetura de autenticacao em todos os servicos.")

    assert result.level == "C3"
    assert result.kind == "architecture"
    assert "superpowers:writing-plans" in result.pipeline
    assert "superpowers:requesting-code-review" in result.pipeline


def test_review_is_distinct_from_implementation():
    result = classify_prompt("Faça uma review deste PR e aponte riscos.")

    assert result.level == "CR"
    assert result.kind == "review"
    assert result.pipeline == ["superpowers:verification-before-completion"]


def test_docs_sensitive_prompt_uses_docs_pipeline():
    result = classify_prompt("Como configuro Pydantic v2 com FastAPI usando a API atual?")

    assert result.level == "DOCS"
    assert result.kind == "api-docs"
    assert result.pipeline[0] == "superpowers:verification-before-completion"


def test_openai_docs_prompt_uses_the_installed_openai_docs_skill():
    result = classify_prompt("Consulte a documentação atual do Codex MCP.")

    assert result.level == "DOCS"
    assert result.pipeline[0] == "openai-docs"


def test_pipelines_contain_no_unqualified_or_ghost_skill_names():
    prompts = [
        "Corrija o bug de login.",
        "Implemente exportação CSV.",
        "Refatore a arquitetura em todos os serviços.",
        "Faça review deste PR.",
        "Como configuro Pydantic v2 com FastAPI usando a API atual?",
    ]

    for prompt in prompts:
        assert all(":" in skill or skill == "openai-docs" for skill in classify_prompt(prompt).pipeline)


def test_task_switch_detected():
    result = classify_prompt("Nova tarefa: implementa um endpoint para cobrancas.")

    assert result.is_task_switch is True
    assert result.level in {"C2", "C3"}
