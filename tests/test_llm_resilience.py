import asyncio

import pytest

from backlogguard.llm import (
    FakeProvider,
    ProviderConfigurationError,
    RateLimitError,
    generate_with_resilience,
    generate_with_resilience_sync,
)


def test_sync_reintenta_ante_rate_limit():
    provider = FakeProvider(delay_seconds=0, failures=["rate_limit"])
    events = []
    outcome = generate_with_resilience_sync(
        provider, "Hola", max_retries=2, base_delay_seconds=0, on_retry=events.append
    )
    assert outcome.attempts == 2 and outcome.retries[0].error_type == "RateLimitError"
    assert len(events) == 1


def test_sync_agota_reintentos():
    provider = FakeProvider(delay_seconds=0, failures=["rate_limit"] * 3)
    with pytest.raises(RateLimitError):
        generate_with_resilience_sync(provider, "Hola", max_retries=2, base_delay_seconds=0)


def test_sync_no_reintenta_errores_de_configuracion():
    provider = FakeProvider(delay_seconds=0, failures=["config", "config"])
    with pytest.raises(ProviderConfigurationError):
        generate_with_resilience_sync(provider, "Hola", max_retries=2, base_delay_seconds=0)
    assert provider.failures == ["config"]


def test_sync_backoff_exponencial():
    provider = FakeProvider(delay_seconds=0, failures=["transient", "transient"])
    outcome = generate_with_resilience_sync(provider, "Hola", max_retries=2, base_delay_seconds=0.001)
    assert [event.next_delay_seconds for event in outcome.retries] == [0.001, 0.002]


def test_async_reintenta_y_respeta_el_curso():
    provider = FakeProvider(delay_seconds=0.01, failures=["rate_limit"])
    outcome = asyncio.run(
        generate_with_resilience(provider, "Hola", timeout_seconds=0.5, max_retries=1, base_delay_seconds=0)
    )
    assert outcome.attempts == 2


def test_async_timeout_se_convierte_en_error_transitorio():
    provider = FakeProvider(delay_seconds=0.3)
    with pytest.raises(Exception) as caught:
        asyncio.run(
            generate_with_resilience(provider, "Hola", timeout_seconds=0.01, max_retries=0, base_delay_seconds=0)
        )
    assert type(caught.value).__name__ == "ProviderTimeoutError"
