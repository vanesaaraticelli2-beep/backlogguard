"""Errores de proveedores de LLM (clase 3 del curso)."""
from __future__ import annotations


class LLMError(Exception):
    """Base de los errores de la capa de LLM."""


class ProviderConfigurationError(LLMError):
    """Credencial ausente o inválida: no se reintenta."""


class InvalidRequestError(LLMError):
    """Pedido mal formado: no se reintenta."""


class InvalidProviderResponseError(LLMError):
    """El proveedor respondió vacío, truncado, rechazado o fuera de contrato."""


class TransientProviderError(LLMError):
    """Fallo transitorio del proveedor: admite reintento."""


class RateLimitError(TransientProviderError):
    """429: demasiadas solicitudes."""


class ProviderTimeoutError(TransientProviderError):
    """La llamada superó el tiempo máximo."""


class PartialStreamError(LLMError):
    """Un stream falló después de emitir texto."""
