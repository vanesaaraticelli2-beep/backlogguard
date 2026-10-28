"""Catálogo de las 16 Tools del sistema y su visibilidad por rol.

Los handlers son marcadores: cada agente reemplaza el suyo cuando se construye.
Ahora existen para poder probar la política de visibilidad con las Tools reales.
"""
from __future__ import annotations

from typing import Any, Callable

from pydantic import BaseModel, ConfigDict

from backlogguard.board import AgentRole
from backlogguard.tools.models import ExecutionContext, ToolKind, ToolResult
from backlogguard.tools.registry import ToolRegistry
from backlogguard.tools.tool import Tool


class ExecutePlanArgs(BaseModel):
    model_config = ConfigDict(extra="forbid")

    plan_hash: str


def _not_implemented(name: str):
    def handler(args: dict) -> ToolResult:
        return ToolResult(
            ok=False,
            content=f"{name} todavía no está implementada.",
            metadata={"error_type": "not_implemented"},
        )

    return handler


def approved_plan_guard(context: ExecutionContext, args: dict[str, Any]) -> str | None:
    """Nadie escribe sin plan aprobado: el hash pedido debe ser el que aprobó una persona."""
    if not context.approved_plan_hash:
        return "No hay un plan de publicación aprobado."
    if args.get("plan_hash") != context.approved_plan_hash:
        return "El plan a ejecutar no coincide con el plan aprobado."
    return None


# (nombre, rol dueño, kind, descripción)
_SPECS: list[tuple[str, AgentRole, ToolKind, str]] = [
    ("delegar_tarea", AgentRole.SUPERVISOR, "compute",
     "Asigna una tarea a un agente del equipo."),
    ("escalar_a_persona", AgentRole.SUPERVISOR, "compute",
     "Pausa la corrida y pide una decisión a una persona."),
    ("ingestar_y_fragmentar", AgentRole.REQUERIMIENTOS, "local_write",
     "Fragmenta una fuente con metadata (reunión, fecha, orador, tipo) y la indexa."),
    ("buscar_en_fuentes", AgentRole.REQUERIMIENTOS, "read",
     "Busca fragmentos relevantes en reuniones y minutas (evidencia). La preventa (línea base) solo se incluye si se la pide."),
    ("redactar_historia", AgentRole.REQUERIMIENTOS, "local_write",
     "Redacta una historia (como, quiero, para), con sus escenarios y reglas de aceptación y sus citas, y la deja en el tablero."),
    ("verificar_cita", AgentRole.CRITICO, "read",
     "Verifica que una cita exista textualmente en la fuente."),
    ("buscar_contraevidencia", AgentRole.CRITICO, "read",
     "Busca evidencia en otras reuniones que contradiga una historia."),
    ("evaluar_dor_invest", AgentRole.CRITICO, "compute",
     "Evalúa una historia contra DoR e INVEST."),
    ("comparar_con_preventa", AgentRole.AUDITOR, "read",
     "Compara lo tratado con lo vendido en la preventa."),
    ("detectar_contradicciones", AgentRole.AUDITOR, "read",
     "Detecta contradicciones entre reuniones y distingue decisiones que evolucionaron."),
    ("consultar_decisiones_vigentes", AgentRole.AUDITOR, "read",
     "Consulta las decisiones vigentes de la memoria del proyecto."),
    ("registrar_decision_aprobada", AgentRole.AUDITOR, "local_write",
     "Registra en la memoria del proyecto una decisión aprobada por una persona."),
    ("buscar_en_backlog", AgentRole.INTEGRACION, "read",
     "Busca work items existentes en el backlog."),
    ("armar_plan_dry_run", AgentRole.INTEGRACION, "draft",
     "Arma el plan de publicación (crear, actualizar, vincular u omitir) sin ejecutarlo."),
    ("revalidar_plan", AgentRole.INTEGRACION, "read",
     "Revalida el plan contra el backlog actual comparando su hash."),
    ("ejecutar_plan_aprobado", AgentRole.INTEGRACION, "write",
     "Publica en el backlog solo el plan aprobado, con clave de idempotencia por ítem."),
]


def build_catalog_registry(
    implementations: dict[str, tuple] | None = None,
) -> ToolRegistry:
    """Registry con las 16 Tools; cada una visible solo para su rol.

    `implementations` reemplaza el marcador de una Tool por su handler real:
    {nombre: (handler, args_model, idempotente[, guarda de autorización])}.
    """
    implementations = implementations or {}
    unknown = set(implementations) - {spec[0] for spec in _SPECS}
    if unknown:
        raise ValueError(f"Tools que no están en el catálogo: {sorted(unknown)}")
    registry = ToolRegistry()
    for name, role, kind, description in _SPECS:
        is_publish = name == "ejecutar_plan_aprobado"
        handler, args_model, idempotent, *guard = implementations.get(
            name, (_not_implemented(name), ExecutePlanArgs if is_publish else None, not is_publish)
        )
        registry.register(
            Tool(
                name=name,
                description=description,
                kind=kind,
                fn=handler,
                args_model=args_model,
                idempotent=idempotent,
                visible_roles={role},
                authorize=approved_plan_guard if is_publish else (guard[0] if guard else None),
            )
        )
    return registry
