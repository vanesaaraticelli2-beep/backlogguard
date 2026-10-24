"""Proveedores de LLM detrás de un contrato común (clase 3 del curso).

`FakeProvider` y `GeminiProvider` siguen el curso. Adaptaciones: `FakeProvider`
admite respuestas guionadas y registra los prompts; el contrato se limita a
`generate` y `agenerate` (el streaming queda fuera de esta etapa). Fuera del
curso: `AnthropicProvider`.
"""
from __future__ import annotations

import asyncio
import time
from dataclasses import asdict, dataclass
from typing import Any, Protocol

from backlogguard.llm.errors import (
    InvalidProviderResponseError,
    InvalidRequestError,
    LLMError,
    ProviderConfigurationError,
    ProviderTimeoutError,
    RateLimitError,
    TransientProviderError,
)
from backlogguard.llm.model_config import ModelSpec
from backlogguard.llm.settings import Settings


@dataclass(frozen=True)
class GenerationResult:
    text: str
    model: str
    provider: str
    latency_ms: float
    input_tokens: int
    output_tokens: int
    finish_reason: str = "stop"

    def to_dict(self) -> dict:
        return asdict(self)


class LLMProvider(Protocol):
    def generate(
        self,
        prompt: str,
        *,
        system: str | None = None,
        temperature: float = 0.2,
    ) -> GenerationResult:
        ...

    async def agenerate(
        self,
        prompt: str,
        *,
        system: str | None = None,
        temperature: float = 0.2,
    ) -> GenerationResult:
        ...


class FakeProvider:
    """Provider determinístico para aprender y testear sin red ni costo."""

    def __init__(
        self,
        model: str = "fake-llm",
        *,
        delay_seconds: float = 0.03,
        failures: list[str] | None = None,
        responses: list[str] | None = None,
    ):
        self.model = model
        self.delay_seconds = delay_seconds
        self.failures = list(failures or [])
        self.responses = list(responses or [])
        self.prompts: list[str] = []
        self.systems: list[str | None] = []

    def _validate(self, prompt: str) -> None:
        if not isinstance(prompt, str) or not prompt.strip():
            raise InvalidRequestError("El prompt no puede estar vacío")

    def _maybe_fail(self) -> None:
        if not self.failures:
            return
        failure = self.failures.pop(0)
        mapping = {
            "rate_limit": RateLimitError("429 simulado: demasiadas solicitudes"),
            "transient": TransientProviderError("503 simulado: proveedor no disponible"),
            "timeout": ProviderTimeoutError("timeout simulado por el provider"),
            "empty": InvalidProviderResponseError("respuesta simulada vacía"),
            "config": ProviderConfigurationError("credencial simulada inválida"),
        }
        raise mapping[failure]

    def _answer(self, prompt: str) -> str:
        if self.responses:
            return self.responses.pop(0)
        last_line = next(
            (line.strip() for line in reversed(prompt.splitlines()) if line.strip()),
            prompt.strip(),
        )
        return f"Respuesta simulada para: {last_line[:120]}"

    def _result(self, prompt: str, started: float) -> GenerationResult:
        text = self._answer(prompt)
        return GenerationResult(
            text=text,
            model=self.model,
            provider="fake",
            latency_ms=round((time.perf_counter() - started) * 1000, 2),
            input_tokens=max(1, len(prompt.split())),
            output_tokens=max(1, len(text.split())),
        )

    def generate(self, prompt: str, *, system: str | None = None, temperature: float = 0.2) -> GenerationResult:
        self._validate(prompt)
        self.prompts.append(prompt)
        self.systems.append(system)
        started = time.perf_counter()
        time.sleep(self.delay_seconds)
        self._maybe_fail()
        return self._result(prompt, started)

    async def agenerate(self, prompt: str, *, system: str | None = None, temperature: float = 0.2) -> GenerationResult:
        self._validate(prompt)
        self.prompts.append(prompt)
        self.systems.append(system)
        started = time.perf_counter()
        await asyncio.sleep(self.delay_seconds)
        self._maybe_fail()
        return self._result(prompt, started)


class GeminiProvider:
    """Adaptador para Google Gen AI SDK (clase 3)."""

    def __init__(self, api_key: str | None, model: str, *, client: Any = None):
        self.model = model
        if client is None:
            if not api_key:
                raise ProviderConfigurationError("Falta GEMINI_API_KEY")
            from google import genai

            client = genai.Client(api_key=api_key, http_options=self._http_options())
        self.client = client

    @staticmethod
    def _http_options():
        """Sin reintentos internos del SDK: la capa de resiliencia es la única que reintenta."""
        from google.genai import types

        return types.HttpOptions(retry_options=types.HttpRetryOptions(attempts=1))

    @staticmethod
    def _map_exception(exc: Exception) -> Exception:
        text = str(exc).lower()
        if "429" in text or "rate limit" in text or "resource exhausted" in text:
            return RateLimitError(str(exc))
        if "timeout" in text or "timed out" in text:
            return ProviderTimeoutError(str(exc))
        if "401" in text or "403" in text or "api key" in text:
            return ProviderConfigurationError(str(exc))
        return TransientProviderError(str(exc))

    @staticmethod
    def _config(system: str | None, temperature: float):
        from google.genai import types

        return types.GenerateContentConfig(system_instruction=system, temperature=temperature)

    @staticmethod
    def _usage(response) -> tuple[int, int]:
        usage = getattr(response, "usage_metadata", None)
        return (
            int(getattr(usage, "prompt_token_count", 0) or 0),
            int(getattr(usage, "candidates_token_count", 0) or 0),
        )

    def _normalize(self, response, started: float) -> GenerationResult:
        text = response.text or ""
        if not text.strip():
            raise InvalidProviderResponseError("Gemini devolvió texto vacío")
        input_tokens, output_tokens = self._usage(response)
        return GenerationResult(
            text=text,
            model=self.model,
            provider="gemini",
            latency_ms=round((time.perf_counter() - started) * 1000, 2),
            input_tokens=input_tokens,
            output_tokens=output_tokens,
        )

    def generate(self, prompt: str, *, system: str | None = None, temperature: float = 0.2) -> GenerationResult:
        if not prompt.strip():
            raise InvalidRequestError("El prompt no puede estar vacío")
        started = time.perf_counter()
        try:
            response = self.client.models.generate_content(
                model=self.model,
                contents=prompt,
                config=self._config(system, temperature),
            )
            return self._normalize(response, started)
        except Exception as exc:
            if isinstance(exc, LLMError):
                raise
            raise self._map_exception(exc) from exc

    async def agenerate(self, prompt: str, *, system: str | None = None, temperature: float = 0.2) -> GenerationResult:
        if not prompt.strip():
            raise InvalidRequestError("El prompt no puede estar vacío")
        started = time.perf_counter()
        try:
            response = await self.client.aio.models.generate_content(
                model=self.model,
                contents=prompt,
                config=self._config(system, temperature),
            )
            return self._normalize(response, started)
        except Exception as exc:
            if isinstance(exc, LLMError):
                raise
            raise self._map_exception(exc) from exc


_ANTHROPIC_ERRORS = {
    "RateLimitError": RateLimitError,
    "APITimeoutError": ProviderTimeoutError,
    "AuthenticationError": ProviderConfigurationError,
    "PermissionDeniedError": ProviderConfigurationError,
    "BadRequestError": InvalidRequestError,
    "NotFoundError": InvalidRequestError,
    "UnprocessableEntityError": InvalidRequestError,
    "InternalServerError": TransientProviderError,
    "APIConnectionError": TransientProviderError,
}


class AnthropicProvider:
    """Adaptador para Claude (fuera del curso; misma estructura que `GeminiProvider`).

    No envía `temperature`, `top_p` ni `top_k`: la API los rechaza con 400 desde
    el 2026-10-21. El parámetro `temperature` se conserva solo por el contrato
    común. Los reintentos los maneja la capa de resiliencia, no el SDK.
    """

    def __init__(
        self,
        api_key: str | None,
        model: str,
        *,
        effort: str | None = None,
        max_output_tokens: int = 16000,
        timeout_seconds: float = 60.0,
        client: Any = None,
        async_client: Any = None,
    ):
        self.model = model
        self.effort = effort
        self.max_output_tokens = max_output_tokens
        if client is None:
            if not api_key:
                raise ProviderConfigurationError("Falta ANTHROPIC_API_KEY")
            import anthropic

            client = anthropic.Anthropic(api_key=api_key, timeout=timeout_seconds, max_retries=0)
            async_client = anthropic.AsyncAnthropic(api_key=api_key, timeout=timeout_seconds, max_retries=0)
        self.client = client
        self.async_client = async_client

    @staticmethod
    def _map_exception(exc: Exception) -> Exception:
        for cls in type(exc).__mro__:
            mapped = _ANTHROPIC_ERRORS.get(cls.__name__)
            if mapped is not None:
                return mapped(str(exc))
        return TransientProviderError(str(exc))

    def _request(self, prompt: str, system: str | None) -> dict[str, Any]:
        request: dict[str, Any] = {
            "model": self.model,
            "max_tokens": self.max_output_tokens,
            "messages": [{"role": "user", "content": prompt}],
        }
        if system:
            request["system"] = system
        if self.effort:
            request["output_config"] = {"effort": self.effort}
        return request

    def _normalize(self, response, started: float) -> GenerationResult:
        if response.stop_reason == "refusal":
            details = getattr(response, "stop_details", None)
            category = getattr(details, "category", None)
            raise InvalidProviderResponseError(f"Claude rechazó el pedido (categoría: {category})")
        text = "".join(block.text for block in response.content if block.type == "text")
        if not text.strip():
            raise InvalidProviderResponseError("Claude devolvió texto vacío")
        return GenerationResult(
            text=text,
            model=self.model,
            provider="anthropic",
            latency_ms=round((time.perf_counter() - started) * 1000, 2),
            input_tokens=int(getattr(response.usage, "input_tokens", 0) or 0),
            output_tokens=int(getattr(response.usage, "output_tokens", 0) or 0),
            finish_reason=str(response.stop_reason or "stop"),
        )

    def generate(self, prompt: str, *, system: str | None = None, temperature: float = 0.2) -> GenerationResult:
        if not prompt.strip():
            raise InvalidRequestError("El prompt no puede estar vacío")
        started = time.perf_counter()
        try:
            response = self.client.messages.create(**self._request(prompt, system))
            return self._normalize(response, started)
        except Exception as exc:
            if isinstance(exc, LLMError):
                raise
            raise self._map_exception(exc) from exc

    async def agenerate(self, prompt: str, *, system: str | None = None, temperature: float = 0.2) -> GenerationResult:
        if not prompt.strip():
            raise InvalidRequestError("El prompt no puede estar vacío")
        started = time.perf_counter()
        try:
            response = await self.async_client.messages.create(**self._request(prompt, system))
            return self._normalize(response, started)
        except Exception as exc:
            if isinstance(exc, LLMError):
                raise
            raise self._map_exception(exc) from exc


def build_provider(spec: ModelSpec, settings: Settings) -> LLMProvider:
    """Proveedor para un agente. Con `live_mode` apagado siempre es el falso (clase 3)."""
    if not settings.live_mode or spec.provider == "fake":
        return FakeProvider(model=f"fake:{spec.model}")
    if spec.provider == "anthropic":
        return AnthropicProvider(
            settings.anthropic_key_value(),
            spec.model,
            effort=spec.effort,
            timeout_seconds=settings.request_timeout_seconds,
        )
    return GeminiProvider(settings.gemini_key_value(), spec.model)
