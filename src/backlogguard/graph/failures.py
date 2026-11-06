"""Traduce la falla de un modelo a una frase que la persona usuaria pueda accionar.

El texto original sigue en la traza; esto solo cubre las causas que no se arreglan en el código (clave, crédito).
"""
from __future__ import annotations

import re


def explain_llm_failure(text: str) -> str | None:
    """Mensaje claro si el texto de un error es de credenciales o de crédito; `None` si es otra cosa."""
    low = text.lower()
    provider = "Gemini" if ("gemini" in low or "api key not valid" in low) else "Anthropic"
    if any(mark in low for mark in ("usage limits", "regain access")):
        when = re.search(r"regain access on (\d{4}-\d{2}-\d{2})", low)
        return (
            f"La cuenta de {provider} llegó al límite de gasto que tiene configurado"
            + (f" (se libera el {when[1]})" if when else "")
            + ". Subí el límite en console.anthropic.com → Settings → Limits y volvé a iniciar la corrida."
        )
    if any(mark in low for mark in ("credit balance", "billing", "insufficient_quota")):
        return f"La cuenta de {provider} no tiene crédito disponible. Cargá saldo y volvé a iniciar la corrida."
    if any(mark in low for mark in ("error code: 401", "authentication_error", "invalid x-api-key", "api key not valid", "falta anthropic_api_key", "falta gemini_api_key", "permission_denied")):
        return (
            f"La clave de {provider} fue rechazada o falta. Revisá {provider.upper()}_API_KEY en el archivo .env, "
            "reiniciá la aplicación y volvé a iniciar la corrida."
        )
    return None


def account_blocked(text: str) -> bool:
    """¿El error deja a la cuenta sin poder usar el modelo (límite de gasto, saldo o clave)? Entonces no tiene sentido seguir la corrida."""
    return explain_llm_failure(text) is not None


def first_explained(texts: list[str]) -> str | None:
    return next((message for text in texts if (message := explain_llm_failure(text))), None)
