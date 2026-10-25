"""Contrato de acceso al backlog (Azure DevOps).

`BacklogGateway` es la única puerta al backlog externo. Hoy la implementa `SimulatedBacklog`; el
cliente MCP real se enchufará aquí después de las clases de noviembre (fuera del curso por ahora).
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


class BacklogError(RuntimeError):
    """Falla al hablar con el backlog."""


class ConflictError(BacklogError):
    """La versión del work item cambió desde que se armó el plan."""


class BacklogTimeout(BacklogError):
    """No se supo si la operación se aplicó (por ejemplo, se perdió la respuesta)."""


class BacklogGateway(Protocol):
    def search(self, *, text: str | None = None, tag: str | None = None) -> list[WorkItem]: ...

    def get(self, work_item_id: int) -> WorkItem | None: ...

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
