"""Policy gate: qué Tools ve cada agente y qué llamadas se autorizan (clase 9 del curso).

La autorización pertenece a `ToolPolicy` y `ToolRegistry`, no a las skills ni a
los archivos de instrucciones (clase 10).
"""
from __future__ import annotations

from typing import TYPE_CHECKING, Any

from backlogguard.board import AgentRole
from backlogguard.tools.models import ExecutionContext
from backlogguard.tools.tool import Tool

if TYPE_CHECKING:
    from backlogguard.tools.registry import ToolRegistry


class ToolPolicy:
    """Decide qué Tools son visibles y autoriza llamadas concretas."""

    KINDS_BY_ROLE = {
        AgentRole.SUPERVISOR: {"read", "compute"},
        AgentRole.REQUERIMIENTOS: {"read", "compute", "local_write"},
        AgentRole.CRITICO: {"read", "compute"},
        AgentRole.AUDITOR: {"read", "compute", "local_write"},
        AgentRole.INTEGRACION: {
            "read",
            "compute",
            "draft",
            "external_effect",
            "write",
        },
    }

    def allowed_tools(
        self,
        registry: "ToolRegistry",
        context: ExecutionContext,
    ) -> list[Tool]:
        """Filtra las Tools visibles para un contexto."""
        return self.allowed_tools_from_list(
            list(registry.tools.values()),
            context,
        )

    def authorize(
        self,
        context: ExecutionContext,
        tool: Tool,
        args: dict[str, Any],
    ) -> str | None:
        """Autoriza una llamada concreta después de validar argumentos.

        Returns:
            `None` si la llamada está autorizada; texto explicativo si se rechaza.
        """
        visible = {
            item.name
            for item in self.allowed_tools_from_list([tool], context)
        }
        if tool.name not in visible:
            return "La Tool no está habilitada para este contexto."

        if tool.authorize_guard is not None:
            return tool.authorize_guard(context, args)

        return None

    def allowed_tools_from_list(
        self,
        tools: list[Tool],
        context: ExecutionContext,
    ) -> list[Tool]:
        """Aplica reglas de rol, flags y visibilidad a una lista de Tools (mínimo privilegio)."""
        allowed_kinds = set(self.KINDS_BY_ROLE[context.role])

        if not context.allow_drafts:
            allowed_kinds.discard("draft")

        if not context.allow_external_writes:
            allowed_kinds.discard("external_effect")
            allowed_kinds.discard("write")

        return [
            tool
            for tool in tools
            if tool.kind in allowed_kinds
            and (
                tool.visible_roles is None
                or context.role in tool.visible_roles
            )
        ]
