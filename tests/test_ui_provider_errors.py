import pytest

streamlit_testing = pytest.importorskip("streamlit.testing.v1")

from backlogguard.llm.errors import InvalidRequestError, ProviderConfigurationError
from backlogguard.ui.app import _provider_error_copy


def _show_saved_error():
    from backlogguard.ui.app import _show_provider_error

    _show_provider_error("provider_error")


def test_credit_error_becomes_an_actionable_message_without_raw_provider_details():
    raw_error = (
        "Error code: 400 - Your credit balance is too low to access the Anthropic API"
    )
    title, message = _provider_error_copy(InvalidRequestError(raw_error))

    assert title == "La cuenta de API no tiene crédito disponible"
    assert "Cargá saldo" in message
    assert raw_error not in message


def test_missing_or_rejected_api_key_is_presented_without_traceback():
    title, message = _provider_error_copy(
        ProviderConfigurationError("Error code: 401 - invalid x-api-key")
    )

    assert title == "El proveedor rechazó el acceso"
    assert "ANTHROPIC_API_KEY" in message
    assert "401" not in message and "invalid x-api-key" not in message


def test_provider_error_card_never_renders_the_raw_exception():
    raw_error = "SDK traceback and private provider response"
    at = streamlit_testing.AppTest.from_function(_show_saved_error, default_timeout=30)
    at.session_state["provider_error"] = {
        "title": "La cuenta de API no tiene crédito disponible",
        "message": "Cargá saldo y volvé a intentar.",
    }

    at.run()

    rendered = "\n".join(element.value for element in at.markdown)
    assert "La cuenta de API no tiene crédito disponible" in rendered
    assert raw_error not in rendered
    assert not at.exception
