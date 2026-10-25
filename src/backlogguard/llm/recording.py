"""Grabación y reproducción de corridas (modo demo sin costo). Fuera del curso.

Una corrida real puede grabarse: las respuestas de cada modelo, en orden y por agente. Reproducirla arma
proveedores guionados (`FakeProvider`) que devuelven esas mismas respuestas, así que el recorrido es el mismo,
sin red, sin claves y sin costo. Sirve para la demo estable, las pruebas de la pantalla y el video de respaldo.

La reproducción depende de que el código haga las mismas llamadas en el mismo orden: si el flujo cambia,
hay que volver a grabar (un test lo detecta).
"""
from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

from pydantic import BaseModel, Field

from backlogguard.llm.providers import FakeProvider, GenerationResult, LLMProvider

ROLES = ("supervisor", "requerimientos", "critico", "auditor", "integracion")


class Recording(BaseModel):
    version: int = 1
    recorded_at: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    objective: str = ""
    models: dict[str, str] = Field(default_factory=dict)
    responses: dict[str, list[str]] = Field(default_factory=lambda: {role: [] for role in ROLES})

    def save(self, path: str | Path) -> None:
        target = Path(path)
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(self.model_dump_json(indent=2), encoding="utf-8")

    @classmethod
    def load(cls, path: str | Path) -> Recording:
        return cls.model_validate(json.loads(Path(path).read_text(encoding="utf-8")))


class RecordingProvider:
    """Envuelve un proveedor y anota cada respuesta exitosa. Los fallos no se graban (se reintentan igual)."""

    def __init__(self, inner: LLMProvider, role: str, recording: Recording):
        self.inner, self.role, self.recording = inner, role, recording
        self.model = getattr(inner, "model", "?")
        recording.models[role] = self.model

    def _keep(self, result: GenerationResult) -> GenerationResult:
        self.recording.responses[self.role].append(result.text)
        return result

    def generate(self, prompt: str, *, system: str | None = None, temperature: float = 0.2) -> GenerationResult:
        return self._keep(self.inner.generate(prompt, system=system, temperature=temperature))

    async def agenerate(self, prompt: str, *, system: str | None = None, temperature: float = 0.2) -> GenerationResult:
        return self._keep(await self.inner.agenerate(prompt, system=system, temperature=temperature))


def recording_providers(providers, recording: Recording):
    """Mismos proveedores, pero anotando lo que responden."""
    return type(providers)(**{role: RecordingProvider(getattr(providers, role), role, recording) for role in ROLES})


def replay_providers(recording: Recording, *, delay_seconds: float = 0.0):
    """Proveedores guionados que repiten, en orden, las respuestas grabadas de cada agente."""
    from backlogguard.graph.deps import Providers

    return Providers(
        **{
            role: FakeProvider(model=f"replay:{recording.models.get(role, role)}", delay_seconds=delay_seconds, responses=list(recording.responses[role]))
            for role in ROLES
        }
    )
