import asyncio
from types import SimpleNamespace

import pytest

from backlogguard.llm import (
    AnthropicProvider,
    FakeProvider,
    GeminiProvider,
    InvalidProviderResponseError,
    InvalidRequestError,
    ProviderConfigurationError,
    ProviderTimeoutError,
    RateLimitError,
    TransientProviderError,
)


def test_fake_responde_con_el_contrato_comun():
    result = FakeProvider(delay_seconds=0).generate("Hola equipo")
    assert result.provider == "fake" and result.text.startswith("Respuesta simulada")
    assert result.input_tokens >= 1 and result.output_tokens >= 1


def test_fake_prompt_vacio():
    with pytest.raises(InvalidRequestError):
        FakeProvider(delay_seconds=0).generate("   ")


@pytest.mark.parametrize(
    "failure,error",
    [
        ("rate_limit", RateLimitError),
        ("transient", TransientProviderError),
        ("timeout", ProviderTimeoutError),
        ("empty", InvalidProviderResponseError),
        ("config", ProviderConfigurationError),
    ],
)
def test_fake_inyecta_fallos(failure, error):
    with pytest.raises(error):
        FakeProvider(delay_seconds=0, failures=[failure]).generate("Hola")


def test_fake_respuestas_guionadas_y_registro_de_prompts():
    provider = FakeProvider(delay_seconds=0, responses=["uno", "dos"])
    assert provider.generate("a", system="S").text == "uno"
    assert provider.generate("b").text == "dos"
    assert provider.prompts == ["a", "b"] and provider.systems == ["S", None]


def test_fake_async():
    result = asyncio.run(FakeProvider(delay_seconds=0).agenerate("Hola"))
    assert result.provider == "fake"


# ---- Anthropic (cliente simulado, sin red) ----


class StubMessages:
    def __init__(self, response=None, error=None):
        self.response, self.error, self.calls = response, error, []

    def create(self, **kwargs):
        self.calls.append(kwargs)
        if self.error:
            raise self.error
        return self.response


def claude_response(text="OK", stop_reason="end_turn", blocks=None):
    content = blocks if blocks is not None else [SimpleNamespace(type="text", text=text)]
    return SimpleNamespace(
        content=content,
        stop_reason=stop_reason,
        stop_details=SimpleNamespace(category="cyber"),
        usage=SimpleNamespace(input_tokens=11, output_tokens=7),
    )


def claude(response=None, error=None, **kwargs):
    messages = StubMessages(response, error)
    provider = AnthropicProvider(None, "claude-sonnet-5-5", client=SimpleNamespace(messages=messages), **kwargs)
    return provider, messages


def test_claude_normaliza_texto_y_tokens():
    provider, _ = claude(claude_response("Hola"))
    result = provider.generate("Decime hola")
    assert (result.text, result.provider, result.input_tokens, result.output_tokens) == ("Hola", "anthropic", 11, 7)


def test_claude_no_envia_parametros_de_muestreo():
    provider, messages = claude(claude_response(), effort="low")
    provider.generate("Hola", system="Sé breve", temperature=0.9)
    request = messages.calls[0]
    assert not {"temperature", "top_p", "top_k"} & set(request)
    assert request["system"] == "Sé breve"
    assert request["output_config"] == {"effort": "low"}
    assert request["model"] == "claude-sonnet-5-5"


def test_claude_sin_system_ni_effort_no_los_envia():
    provider, messages = claude(claude_response())
    provider.generate("Hola")
    assert "system" not in messages.calls[0] and "output_config" not in messages.calls[0]


def test_claude_ignora_bloques_que_no_son_texto():
    blocks = [SimpleNamespace(type="thinking", thinking=""), SimpleNamespace(type="text", text="Listo")]
    provider, _ = claude(claude_response(blocks=blocks))
    assert provider.generate("Hola").text == "Listo"


def test_claude_refusal_y_texto_vacio():
    provider, _ = claude(claude_response(stop_reason="refusal", blocks=[]))
    with pytest.raises(InvalidProviderResponseError, match="rechazó"):
        provider.generate("Hola")
    provider, _ = claude(claude_response(text="  "))
    with pytest.raises(InvalidProviderResponseError):
        provider.generate("Hola")


def make_error(name, status=None):
    return type(name, (Exception,), {"status_code": status})("falló")


@pytest.mark.parametrize(
    "name,expected",
    [
        ("RateLimitError", RateLimitError),
        ("APITimeoutError", ProviderTimeoutError),
        ("AuthenticationError", ProviderConfigurationError),
        ("PermissionDeniedError", ProviderConfigurationError),
        ("BadRequestError", InvalidRequestError),
        ("InternalServerError", TransientProviderError),
        ("APIConnectionError", TransientProviderError),
        ("ErrorDesconocido", TransientProviderError),
    ],
)
def test_claude_mapea_errores_del_sdk(name, expected):
    provider, _ = claude(error=make_error(name))
    with pytest.raises(expected):
        provider.generate("Hola")


def test_claude_requiere_clave_si_no_hay_cliente():
    with pytest.raises(ProviderConfigurationError):
        AnthropicProvider(None, "claude-sonnet-5-5")


def test_claude_async():
    class AsyncMessages:
        async def create(self, **kwargs):
            return claude_response("Async")

    provider = AnthropicProvider(
        None, "claude-sonnet-5-5", client=object(), async_client=SimpleNamespace(messages=AsyncMessages())
    )
    assert asyncio.run(provider.agenerate("Hola")).text == "Async"


# ---- Gemini (cliente simulado) ----


def test_gemini_requiere_clave_si_no_hay_cliente():
    with pytest.raises(ProviderConfigurationError):
        GeminiProvider(None, "gemini-3.8-flash")


def test_gemini_mapea_errores_por_texto():
    assert isinstance(GeminiProvider._map_exception(Exception("429 Resource exhausted")), RateLimitError)
    assert isinstance(GeminiProvider._map_exception(Exception("request timed out")), ProviderTimeoutError)
    assert isinstance(GeminiProvider._map_exception(Exception("403 API key not valid")), ProviderConfigurationError)
    assert isinstance(GeminiProvider._map_exception(Exception("boom")), TransientProviderError)


def test_gemini_desactiva_los_reintentos_internos_del_sdk():
    pytest.importorskip("google.genai")
    assert GeminiProvider._http_options().retry_options.attempts == 1
    provider = GeminiProvider("g-test", "gemini-3.8-flash")
    assert provider.client is not None


def test_gemini_normaliza_respuesta():
    pytest.importorskip("google.genai")
    usage = SimpleNamespace(prompt_token_count=5, candidates_token_count=3)
    response = SimpleNamespace(text="Hola", usage_metadata=usage)
    client = SimpleNamespace(models=SimpleNamespace(generate_content=lambda **kwargs: response))
    result = GeminiProvider(None, "gemini-3.8-flash", client=client).generate("Hola", system="S")
    assert (result.text, result.provider, result.input_tokens, result.output_tokens) == ("Hola", "gemini", 5, 3)
