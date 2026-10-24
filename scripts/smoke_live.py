"""Prueba real mínima de cada proveedor configurado en config/models.yaml.

Apagada por defecto: solo corre con LIVE_MODE=1 y las claves en .env. Hace una
llamada corta por agente, imprime tokens y un costo estimado.

    $env:LIVE_MODE = "1"; .venv\\Scripts\\python scripts\\smoke_live.py
"""
from __future__ import annotations

import sys
from pathlib import Path

from backlogguard.board import AgentRole
from backlogguard.llm import Settings, build_provider, generate_with_resilience_sync, load_models_config

ROOT = Path(__file__).resolve().parents[1]

# USD por millón de tokens (entrada, salida). Claude: precios vigentes al 2026-10-06.
# Gemini: valores por defecto de la clase 3 del curso (referencia, verificar en el proveedor).
PRICES = {
    "claude-opus-5-5": (4.00, 20.00),
    "claude-sonnet-5-5": (2.00, 10.00),
    "claude-haiku-5-5": (0.10, 0.50),
    "gemini-3.8-flash": (0.25, 1.50),
}


def main() -> int:
    settings = Settings.from_env(ROOT / ".env")
    if not settings.live_mode:
        print("LIVE_MODE=0: no se hacen llamadas reales. Activá LIVE_MODE=1 para correr esta prueba.")
        return 0

    config = load_models_config(ROOT / "config" / "models.yaml")
    total = 0.0
    for role in AgentRole:
        spec = config.for_role(role)
        provider = build_provider(spec, settings)
        outcome = generate_with_resilience_sync(
            provider,
            "Respondé solo con la palabra OK.",
            max_retries=settings.max_retries,
            base_delay_seconds=settings.retry_base_delay_seconds,
        )
        result = outcome.result
        price_in, price_out = PRICES.get(spec.model, (0.0, 0.0))
        cost = (result.input_tokens * price_in + result.output_tokens * price_out) / 1_000_000
        total += cost
        print(
            f"{role.value:15} {spec.provider}/{spec.model:20} "
            f"in={result.input_tokens} out={result.output_tokens} "
            f"{result.latency_ms:.0f}ms ~${cost:.6f} -> {result.text.strip()[:40]!r}"
        )
    print(f"Costo estimado total: ~${total:.6f}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
