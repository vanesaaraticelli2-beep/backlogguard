from backlogguard.agents.loop import run_basic_agent
from backlogguard.graph.failures import explain_llm_failure, first_explained
from backlogguard.llm.errors import ProviderConfigurationError
from backlogguard.tools.registry import ToolRegistry

AUTH = "ProviderConfigurationError: Error code: 401 - {'type': 'error', 'error': {'type': 'authentication_error', 'message': 'invalid x-api-key'}}"


def test_invalid_anthropic_key_is_explained():
    message = explain_llm_failure(AUTH)
    assert "Anthropic" in message and "ANTHROPIC_API_KEY" in message and ".env" in message


def test_gemini_key_and_credit_are_told_apart():
    assert "GEMINI_API_KEY" in explain_llm_failure("API key not valid. Please pass a valid API key (Gemini)")
    assert "crédito" in explain_llm_failure("Your credit balance is too low to access the Anthropic API")


def test_other_failures_are_not_explained():
    assert explain_llm_failure("InvalidProviderResponseError: respuesta vacía") is None
    assert explain_llm_failure("item 4012 no encontrado") is None
    assert first_explained(["otra cosa", AUTH]) is not None and first_explained([]) is None


def test_loop_keeps_the_cause_of_a_model_failure():
    def decide(message, observations):
        raise ProviderConfigurationError("Error code: 401 - invalid x-api-key")

    outcome = run_basic_agent("hola", ToolRegistry(), decide)
    assert outcome["stop_reason"] == "unrecoverable_error"
    assert outcome["error"].startswith("ProviderConfigurationError") and "401" in outcome["error"]
