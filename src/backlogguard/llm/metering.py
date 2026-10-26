"""Medición de uso de los modelos (fuera del curso).

`MeteredProvider` envuelve a un proveedor y anota cada llamada exitosa (tokens de entrada y de salida);
`Meter` permite leer cuánto se gastó entre dos puntos. Así cada tarea de la corrida sabe lo que costó, incluidas
las reparaciones de JSON y los reintentos, sin que cada agente tenga que sumar sus propios tokens.
Los precios viven en `config/pricing.yaml`; con un modelo sin precio se avisa en lugar de inventar un valor.
"""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import yaml

from backlogguard.llm.providers import GenerationResult, LLMProvider

PRICING_PATH = Path(__file__).resolve().parents[3] / "config" / "pricing.yaml"


@dataclass(frozen=True)
class Usage:
    input_tokens: int = 0
    output_tokens: int = 0
    calls: int = 0

    @property
    def tokens(self) -> int:
        return self.input_tokens + self.output_tokens


class Meter:
    def __init__(self) -> None:
        self.input_tokens = 0
        self.output_tokens = 0
        self.calls = 0

    def add(self, result: GenerationResult) -> None:
        self.input_tokens += result.input_tokens
        self.output_tokens += result.output_tokens
        self.calls += 1

    def mark(self) -> Usage:
        return Usage(self.input_tokens, self.output_tokens, self.calls)

    def since(self, mark: Usage) -> Usage:
        return Usage(self.input_tokens - mark.input_tokens, self.output_tokens - mark.output_tokens, self.calls - mark.calls)


class MeteredProvider:
    def __init__(self, inner: LLMProvider, meter: Meter):
        self.inner, self.meter = inner, meter
        self.model = getattr(inner, "model", "?")

    def generate(self, prompt: str, *, system: str | None = None, temperature: float = 0.2) -> GenerationResult:
        result = self.inner.generate(prompt, system=system, temperature=temperature)
        self.meter.add(result)
        return result

    async def agenerate(self, prompt: str, *, system: str | None = None, temperature: float = 0.2) -> GenerationResult:
        result = await self.inner.agenerate(prompt, system=system, temperature=temperature)
        self.meter.add(result)
        return result


def load_pricing(path: Path = PRICING_PATH) -> dict[str, tuple[float, float]]:
    """USD por millón de tokens (entrada, salida) por modelo."""
    if not path.is_file():
        return {}
    data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    return {model: (float(p["input"]), float(p["output"])) for model, p in (data.get("models") or {}).items()}


def estimate_cost(model: str, input_tokens: int, output_tokens: int, pricing: dict[str, tuple[float, float]]) -> float | None:
    """Costo estimado en USD, o `None` si el modelo no tiene precio configurado."""
    price = pricing.get(model.split(":", 1)[-1])  # "replay:claude-opus-5-5" cuesta lo que el modelo grabado
    if price is None:
        return None
    return (input_tokens * price[0] + output_tokens * price[1]) / 1_000_000
