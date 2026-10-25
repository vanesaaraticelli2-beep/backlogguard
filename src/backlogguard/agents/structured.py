"""Salida estructurada de un agente: parseo con una reparación de formato (patrón de la clase 2)."""
from __future__ import annotations

import json
import re
from typing import Callable, TypeVar

from pydantic import ValidationError

from backlogguard.llm.errors import InvalidProviderResponseError
from backlogguard.llm.providers import LLMProvider
from backlogguard.llm.resilience import generate_with_resilience_sync

T = TypeVar("T")
_FENCE = re.compile(r"^```(?:json)?\s*|\s*```$", re.IGNORECASE)


def extract_json(text: str) -> str:
    """Devuelve el objeto JSON contenido en la respuesta, sin cercos de código."""
    cleaned = _FENCE.sub("", text.strip())
    start, end = cleaned.find("{"), cleaned.rfind("}")
    if start == -1 or end == -1:
        raise ValueError("la respuesta no contiene un objeto JSON")
    return cleaned[start : end + 1]


def parse_with_repair(
    answer: str,
    parse: Callable[[str], T],
    *,
    provider: LLMProvider,
    system: str,
    expected_format: str,
    subject: str,
) -> tuple[T, int]:
    """Parsea `answer`; si falla, pide al modelo una sola corrección. Devuelve (valor, tokens gastados)."""
    try:
        return parse(answer), 0
    except (ValueError, ValidationError) as exc:
        repair = generate_with_resilience_sync(
            provider,
            f"Tu respuesta anterior no cumplió el formato: {exc}\n\n"
            f"Respuesta anterior:\n{json.dumps(answer, ensure_ascii=False)}\n\n"
            f"Respondé solo con el JSON pedido, con esta forma: {expected_format}",
            system=system,
        )
        tokens = repair.result.input_tokens + repair.result.output_tokens
        try:
            return parse(repair.result.text), tokens
        except (ValueError, ValidationError) as second:
            raise InvalidProviderResponseError(f"{subject} no devolvió un resultado válido: {second}") from second
