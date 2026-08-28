from harness4codex.classifier import classify_prompt
from harness4codex.contract import ContractSnapshot


def test_simple_question_is_c0():
    result = classify_prompt("Explique rapidamente como este modulo funciona.")

    assert result.level == "C0"
    assert result.kind == "question"
    assert result.pipeline == []


def test_bug_promotes_debugging_and_tdd():
    result = classify_prompt("Corrija este bug: o login quebra quando o token expira.")

    assert result.level == "C1"
    assert result.kind == "bug"
    assert result.pipeline == ["systematic-debugging", "tdd", "verify"]


def test_feature_uses_light_spec_pipeline():
    result = classify_prompt("Implemente exportacao CSV para a tela de relatorios.")

    assert result.level == "C2"
    assert result.kind == "feature"
    assert result.pipeline[0] == "write-spec-light"
    assert result.pipeline[-1] == "verify-against-spec"


def test_architecture_uses_design_and_review():
    result = classify_prompt("Refatore a arquitetura de autenticacao em todos os servicos.")

    assert result.level == "C3"
    assert result.kind == "architecture"
    assert "graph-context" in result.pipeline
    assert "validate-plan" in result.pipeline
    assert result.pipeline[-1] == "verify-multimodel"


def test_review_is_distinct_from_implementation():
    result = classify_prompt("Faça uma review deste PR e aponte riscos.")

    assert result.level == "CR"
    assert result.kind == "review"
    assert result.pipeline == ["code-review", "verify"]


def test_docs_sensitive_prompt_uses_docs_pipeline():
    result = classify_prompt("Como configuro Pydantic v2 com FastAPI usando a API atual?")

    assert result.level == "DOCS"
    assert result.kind == "api-docs"
    assert result.pipeline == ["source-selection", "documentation", "verify"]


def test_openai_docs_prompt_uses_the_installed_openai_docs_skill():
    result = classify_prompt("Consulte a documentação atual do Codex MCP.")

    assert result.level == "DOCS"
    assert result.pipeline == ["source-selection", "documentation", "verify"]


def test_classifier_pipelines_are_the_vendored_contract_pipelines():
    prompts = [
        "Corrija o bug de login.",
        "Implemente exportação CSV.",
        "Refatore a arquitetura em todos os serviços.",
        "Faça review deste PR.",
        "Como configuro Pydantic v2 com FastAPI usando a API atual?",
    ]

    contract = ContractSnapshot.load()
    for prompt in prompts:
        result = classify_prompt(prompt)
        normalized = contract.normalize(result.level, result.kind)
        assert result.pipeline == contract.pipeline(normalized["tier"], normalized["kind"])


def test_task_switch_detected():
    result = classify_prompt("Nova tarefa: implementa um endpoint para cobrancas.")

    assert result.is_task_switch is True
    assert result.level in {"C2", "C3"}
