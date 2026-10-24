"""Contrato de una Tool (clase 9 del curso)."""
from __future__ import annotations

from typing import Any, Callable

from pydantic import BaseModel

from backlogguard.tools.models import (
    VALID_TOOL_KINDS,
    ExecutionContext,
    Role,
    ToolKind,
    ToolResult,
)

AuthorizationGuard = Callable[[ExecutionContext, dict[str, Any]], str | None]


class Tool:
    """Contrato runtime-facing y model-facing de una capacidad del agente."""

    def __init__(
        self,
        name: str,
        description: str,
        kind: ToolKind,
        fn: Callable[[dict], ToolResult],
        args_model: type[BaseModel] | None = None,
        timeout_s: float = 3.0,
        retries: int = 0,
        *,
        backoff_s: float = 0.05,
        idempotent: bool = True,
        visible_roles: set[Role] | None = None,
        authorize: AuthorizationGuard | None = None,
    ):
        """Configura una Tool y sus controles operativos.

        Raises:
            ValueError: Si la configuración operativa es insegura o inválida.
        """
        if kind not in VALID_TOOL_KINDS:
            raise ValueError(f"{name}: kind desconocido: {kind}.")
        if timeout_s <= 0:
            raise ValueError(f"{name}: timeout_s debe ser mayor que 0.")
        if retries < 0:
            raise ValueError(f"{name}: retries no puede ser negativo.")
        if backoff_s < 0:
            raise ValueError(f"{name}: backoff_s no puede ser negativo.")
        if retries > 0 and not idempotent:
            raise ValueError(
                f"{name}: una Tool no idempotente no puede tener retries automáticos "
                "sin una estrategia explícita contra duplicados."
            )

        self.name = name
        self.description = description
        self.kind = kind
        self.fn = fn
        self.args_model = args_model
        self.timeout_s = timeout_s
        self.retries = retries
        self.backoff_s = backoff_s
        self.idempotent = idempotent
        self.visible_roles = visible_roles
        self.authorize_guard = authorize

    @property
    def risk(self) -> str:
        """Devuelve la categoría de riesgo/capacidad usada por la Policy."""
        return self.kind

    def function_declaration(self) -> dict:
        """Construye el contrato model-facing para Function Calling.

        El handler, los permisos y los controles operativos no se exponen al modelo:
        siguen siendo responsabilidad de la aplicación.
        """
        parameters = (
            self.args_model.model_json_schema()
            if self.args_model
            else {"type": "object", "properties": {}}
        )

        parameters.pop("title", None)
        for prop in parameters.get("properties", {}).values():
            prop.pop("title", None)

        return {
            "name": self.name,
            "description": self.description,
            "parameters": parameters,
        }
