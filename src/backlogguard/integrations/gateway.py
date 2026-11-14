"""Contrato de acceso al backlog (Azure DevOps).

`BacklogGateway` es la única puerta al backlog externo; la implementan el simulador y el adaptador REST.
"""
from __future__ import annotations

from typing import Protocol

from pydantic import BaseModel, ConfigDict, Field


class WorkItem(BaseModel):
    """Work item tal como lo ve el plan: lo mínimo que BacklogGuard publica y compara."""

    model_config = ConfigDict(extra="forbid")

    id: int
    type: str
    title: str
    description: str = ""
    acceptance_criteria: list[str] = Field(default_factory=list)
    tags: list[str] = Field(default_factory=list)
    parent_id: int | None = None
    rev: int = 1
    state: str = "New"
    url: str | None = None


class BacklogError(RuntimeError):
    """Falla al hablar con el backlog."""


class BacklogAuthenticationError(BacklogError):
    """La autenticación con el backlog fue rechazada."""


class BacklogPermissionError(BacklogError):
    """La persona autenticada no tiene permisos suficientes."""


class BacklogNotFoundError(BacklogError):
    """No se encontró el recurso solicitado en el backlog."""


class BacklogRateLimitError(BacklogError):
    """El backlog limitó temporalmente las solicitudes."""


class ConflictError(BacklogError):
    """La versión del work item cambió desde que se armó el plan."""


class BacklogTimeout(BacklogError):
    """No se supo si la operación se aplicó (por ejemplo, se perdió la respuesta)."""


class BacklogGateway(Protocol):
    def resolve_work_item_type(self, requested_type: str) -> str: ...

    def list_work_item_states(self, work_item_type: str) -> list[dict[str, str]]: ...

    def reload(self) -> None: ...

    def search(self, *, text: str | None = None, tag: str | None = None) -> list[WorkItem]: ...

    def get(self, work_item_id: int) -> WorkItem | None: ...

    def get_children(self, work_item_id: int) -> list[WorkItem]: ...

    def create(
        self,
        *,
        type: str,
        title: str,
        description: str,
        acceptance_criteria: list[str],
        tags: list[str],
        parent_id: int | None,
    ) -> WorkItem: ...

    def update(
        self,
        work_item_id: int,
        *,
        expected_rev: int,
        title: str,
        description: str,
        acceptance_criteria: list[str],
        tags: list[str],
    ) -> WorkItem: ...

    def link_parent(self, work_item_id: int, parent_id: int, *, expected_rev: int) -> WorkItem: ...

    def transition_state(
        self, work_item_id: int, *, expected_rev: int, state: str
    ) -> WorkItem: ...
