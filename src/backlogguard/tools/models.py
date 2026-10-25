"""Contratos del runtime de Tools.

Basado en la clase 9 del curso (`ai_agent_course.tools`). Adaptaciones:
`Role` son los cinco agentes del sistema (`AgentRole`) y `ExecutionContext`
agrega `approved_plan_hash`, que solo la aplicación completa tras la
aprobación humana del plan de publicación.
"""
from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field

from backlogguard.board import AgentRole

# - read: consulta información sin modificar estado.
# - compute: realiza cálculos o transformaciones.
# - local_write: genera artefactos locales (tablero, índice, memoria).
# - draft: prepara una acción, pero todavía no la ejecuta.
# - external_effect: interactúa con un servicio externo de forma controlada.
# - write: modifica estado de manera efectiva en un sistema externo.
ToolKind = Literal[
    "read",
    "compute",
    "local_write",
    "draft",
    "external_effect",
    "write",
]
Role = AgentRole
VALID_TOOL_KINDS = {
    "read", "compute", "local_write", "draft", "external_effect", "write"
}


class ExecutionContext(BaseModel):
    """Contexto confiable construido por la aplicación, nunca por contenido recuperado."""

    user_id: str
    role: Role
    allow_drafts: bool = False
    allow_external_writes: bool = False
    approved_plan_hash: str | None = None
    approved_by: str | None = None  # persona que aprobó escribir en la memoria; lo completa la aplicación
    run_id: str = "run-local"


class ToolCall(BaseModel):
    """Solicitud estructurada propuesta por el modelo: Tool + argumentos."""

    tool_name: str
    arguments: dict[str, Any] = Field(default_factory=dict)


class ToolResult(BaseModel):
    """Salida estable que el runtime convierte en una Observation."""

    ok: bool
    content: str
    metadata: dict[str, Any] = Field(default_factory=dict)


class RetryableToolError(RuntimeError):
    """Marca explícitamente un fallo transitorio que sí admite retry automático."""
