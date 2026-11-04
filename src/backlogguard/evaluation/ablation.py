"""Ablación: el sistema sin el Crítico o sin el Auditor, para ver qué aporta cada uno.

No toca el grafo: reemplaza al proveedor del agente por uno que no objeta nada o no encuentra nada. Así el recorrido,
el presupuesto y las pausas son los mismos y solo cambia el aporte del agente retirado.
"""
from __future__ import annotations

import json
import re
from dataclasses import replace

from backlogguard.graph.deps import Providers
from backlogguard.llm.providers import GenerationResult

ABLATION_ENV = "BACKLOGGUARD_ABLATE"
VALID = ("critico", "auditor")


def _answer(body: dict, model: str) -> GenerationResult:
    text = json.dumps({"action": "final", "final_answer": json.dumps(body)})
    return GenerationResult(text=text, model=model, provider="ablation", latency_ms=0.0, input_tokens=1, output_tokens=1)


class ApprovingCritic:
    """Crítico retirado: da por sustentado todo ítem sin mirarlo."""

    model = "ablation:sin-critico"

    def generate(self, prompt, *, system=None, temperature=0.2):
        target = re.search(r"Revisá el ítem (\S+) del tablero", prompt)
        body = {"item_id": target.group(1) if target else "", "verdict": "sustentado", "objections": [], "reasoning": "ablación"}
        return _answer(body, self.model)

    async def agenerate(self, prompt, *, system=None, temperature=0.2):
        return self.generate(prompt, system=system, temperature=temperature)


class SilentAuditor:
    """Auditor retirado: no encuentra hallazgos."""

    model = "ablation:sin-auditor"

    def generate(self, prompt, *, system=None, temperature=0.2):
        return _answer({"findings": [], "summary": "ablación"}, self.model)

    async def agenerate(self, prompt, *, system=None, temperature=0.2):
        return self.generate(prompt, system=system, temperature=temperature)


def parse_ablation(value: str | None) -> frozenset[str]:
    names = frozenset(part.strip().casefold() for part in (value or "").split(",") if part.strip())
    unknown = names - set(VALID)
    if unknown:
        raise ValueError(f"{ABLATION_ENV}: valores válidos {', '.join(VALID)}; no reconozco {', '.join(sorted(unknown))}")
    return names


def ablate(providers: Providers, names: frozenset[str]) -> Providers:
    changes = {}
    if "critico" in names:
        changes["critico"] = ApprovingCritic()
    if "auditor" in names:
        changes["auditor"] = SilentAuditor()
    return replace(providers, **changes) if changes else providers
