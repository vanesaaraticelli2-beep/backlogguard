"""Traduce la falla de un modelo a una frase que la persona usuaria pueda accionar.

El texto original sigue en la traza; esto solo cubre las causas que no se arreglan en el código (clave, crédito).
"""
from __future__ import annotations


def explain_llm_failure(text: str) -> str | None:
    """Mensaje claro si el texto de un error es de credenciales o de crédito; `None` si es otra cosa."""
    low = text.lower()
    provider = "Gemini" if ("gemini" in low or "api key not valid" in low) else "Anthropic"
    if any(mark in low for mark in ("credit balance", "billing", "insufficient_quota")):
        return f"La cuenta de {provider} no tiene crédito disponible. Cargá saldo y volvé a iniciar la corrida."
    if any(mark in low for mark in ("error code: 401", "authentication_error", "invalid x-api-key", "api key not valid", "falta anthropic_api_key", "falta gemini_api_key", "permission_denied")):
        return (
            f"La clave de {provider} fue rechazada o falta. Revisá {provider.upper()}_API_KEY en el archivo .env, "
            "reiniciá la aplicación y volvé a iniciar la corrida."
        )
    return None


def first_explained(texts: list[str]) -> str | None:
    return next((message for text in texts if (message := explain_llm_failure(text))), None)
