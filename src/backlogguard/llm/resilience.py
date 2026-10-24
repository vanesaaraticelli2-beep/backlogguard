"""Timeout y reintentos con backoff (clase 3 del curso).

`generate_with_resilience` es la del curso (async). `generate_with_resilience_sync`
es su gemela síncrona para el ciclo del agente de la clase 9, que es síncrono;
el timeout lo aplica el cliente del proveedor.
"""
from __future__ import annotations

import asyncio
import random
import time
from dataclasses import dataclass
from typing import Callable

from backlogguard.llm.errors import (
    ProviderTimeoutError,
    RateLimitError,
    TransientProviderError,
)
from backlogguard.llm.providers import GenerationResult, LLMProvider

RETRYABLE_ERRORS = (RateLimitError, ProviderTimeoutError, TransientProviderError)


@dataclass(frozen=True)
class RetryEvent:
    attempt: int
    error_type: str
    message: str
    next_delay_seconds: float


@dataclass(frozen=True)
class CallOutcome:
    result: GenerationResult
    attempts: int
    retries: tuple[RetryEvent, ...]


def _retry_event(attempt: int, error: Exception, base_delay_seconds: float, jitter: bool) -> RetryEvent:
    delay = base_delay_seconds * (2 ** (attempt - 1))
    if jitter:
        delay *= random.uniform(0.8, 1.2)
    return RetryEvent(
        attempt=attempt,
        error_type=type(error).__name__,
        message=str(error),
        next_delay_seconds=round(delay, 4),
    )


async def generate_with_resilience(
    provider: LLMProvider,
    prompt: str,
    *,
    system: str | None = None,
    temperature: float = 0.2,
    timeout_seconds: float = 20.0,
    max_retries: int = 2,
    base_delay_seconds: float = 0.25,
    jitter: bool = False,
    on_retry: Callable[[RetryEvent], None] | None = None,
) -> CallOutcome:
    retries: list[RetryEvent] = []

    for attempt in range(1, max_retries + 2):
        try:
            result = await asyncio.wait_for(
                provider.agenerate(prompt, system=system, temperature=temperature),
                timeout=timeout_seconds,
            )
            return CallOutcome(result=result, attempts=attempt, retries=tuple(retries))
        except asyncio.TimeoutError:
            error: Exception = ProviderTimeoutError(
                f"La llamada superó {timeout_seconds:.2f} segundos"
            )
        except RETRYABLE_ERRORS as exc:
            error = exc

        if attempt > max_retries:
            raise error

        event = _retry_event(attempt, error, base_delay_seconds, jitter)
        retries.append(event)
        if on_retry:
            on_retry(event)
        await asyncio.sleep(event.next_delay_seconds)

    raise RuntimeError("Estado inalcanzable")


def generate_with_resilience_sync(
    provider: LLMProvider,
    prompt: str,
    *,
    system: str | None = None,
    temperature: float = 0.2,
    max_retries: int = 2,
    base_delay_seconds: float = 0.25,
    jitter: bool = False,
    on_retry: Callable[[RetryEvent], None] | None = None,
) -> CallOutcome:
    retries: list[RetryEvent] = []

    for attempt in range(1, max_retries + 2):
        try:
            result = provider.generate(prompt, system=system, temperature=temperature)
            return CallOutcome(result=result, attempts=attempt, retries=tuple(retries))
        except RETRYABLE_ERRORS as exc:
            error = exc

        if attempt > max_retries:
            raise error

        event = _retry_event(attempt, error, base_delay_seconds, jitter)
        retries.append(event)
        if on_retry:
            on_retry(event)
        time.sleep(event.next_delay_seconds)

    raise RuntimeError("Estado inalcanzable")
