"""Contrato de datos del tablero compartido.

Toda salida de agente se valida contra estos modelos. Las reglas de negocio
(transiciones de estado, citas obligatorias, tope de rondas) viven en código,
no en el prompt.
"""
from __future__ import annotations

from datetime import date, datetime, timezone
from enum import StrEnum

from pydantic import BaseModel, ConfigDict, Field, model_validator

MAX_ROUNDS = 2


class _Strict(BaseModel):
    model_config = ConfigDict(extra="forbid")


class AgentRole(StrEnum):
    SUPERVISOR = "supervisor"
    REQUERIMIENTOS = "requerimientos"
    CRITICO = "critico"
    AUDITOR = "auditor"
    INTEGRACION = "integracion"


class SourceType(StrEnum):
    REUNION = "reunion"
    MINUTA = "minuta"
    PREVENTA = "preventa"


class ItemKind(StrEnum):
    EPICA = "epica"
    HISTORIA = "historia"
    TAREA = "tarea"
    CASO_DE_PRUEBA = "caso_de_prueba"


class ItemState(StrEnum):
    BORRADOR = "borrador"
    OBJETADO = "objetado"
    SUSTENTADO = "sustentado"
    APROBADO = "aprobado"
    EXCLUIDO = "excluido"


class FindingKind(StrEnum):
    CAMBIO_DE_ALCANCE = "cambio_de_alcance"
    CONTRADICCION = "contradiccion"
    TRATADO_NO_VENDIDO = "tratado_no_vendido"
    VENDIDO_NO_TRATADO = "vendido_no_tratado"
    DECISION_EVOLUCIONADA = "decision_evolucionada"


ALLOWED_TRANSITIONS: dict[ItemState, frozenset[ItemState]] = {
    ItemState.BORRADOR: frozenset({ItemState.OBJETADO, ItemState.SUSTENTADO}),
    ItemState.OBJETADO: frozenset({ItemState.SUSTENTADO, ItemState.EXCLUIDO}),
    # Un hallazgo posterior del Auditor puede reabrir un ítem sustentado (aún no aprobado).
    ItemState.SUSTENTADO: frozenset({ItemState.APROBADO, ItemState.EXCLUIDO, ItemState.OBJETADO}),
    ItemState.APROBADO: frozenset(),
    ItemState.EXCLUIDO: frozenset(),
}


class InvalidTransition(ValueError):
    """Transición de estado no permitida o sin los requisitos de trazabilidad."""


class Citation(_Strict):
    """Fragmento de una fuente que sustenta un ítem."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    fragment_id: str = Field(min_length=1)
    quote: str = Field(min_length=1)
    source_name: str = Field(min_length=1, description="Reunión, minuta o documento de origen")
    source_type: SourceType
    source_date: date
    speaker: str | None = None
    page: int | None = Field(default=None, ge=1, description="Página del documento, si la fuente es un PDF")


class Objection(_Strict):
    id: str = Field(min_length=1)
    raised_by: AgentRole
    text: str = Field(min_length=1)
    round: int = Field(ge=1, le=MAX_ROUNDS)
    resolved: bool = False


class Finding(_Strict):
    id: str = Field(min_length=1)
    kind: FindingKind
    raised_by: AgentRole
    addressee: AgentRole
    description: str = Field(min_length=1)
    item_id: str | None = None
    citations: list[Citation] = Field(default_factory=list)


class AgentMessage(_Strict):
    sender: AgentRole
    recipient: AgentRole
    content: str = Field(min_length=1)
    sent_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class BacklogItem(_Strict):
    id: str = Field(min_length=1)
    kind: ItemKind
    title: str = Field(min_length=1)
    description: str = ""
    acceptance_criteria: list[str] = Field(default_factory=list)
    citations: list[Citation] = Field(default_factory=list)
    objections: list[Objection] = Field(default_factory=list)
    state: ItemState = ItemState.BORRADOR
    approved_by: str | None = None
    parent_id: str | None = Field(default=None, description="Ítem padre (por ejemplo, la épica de una historia)")

    @model_validator(mode="after")
    def _traceability(self) -> BacklogItem:
        needs_citation = self.state in (ItemState.SUSTENTADO, ItemState.APROBADO)
        if needs_citation and not self.citations:
            raise ValueError(f"un ítem {self.state.value} requiere al menos una cita")
        if self.state is ItemState.APROBADO and not self.approved_by:
            raise ValueError("un ítem aprobado requiere approved_by")
        return self

    def transition_to(self, new_state: ItemState, *, actor: str | None = None) -> None:
        """Mueve el ítem a `new_state` si el camino es válido y deja traza de quién aprobó."""
        if new_state not in ALLOWED_TRANSITIONS[self.state]:
            raise InvalidTransition(f"{self.state.value} -> {new_state.value} no está permitido")
        if new_state in (ItemState.SUSTENTADO, ItemState.APROBADO) and not self.citations:
            raise InvalidTransition(f"{new_state.value} requiere al menos una cita")
        if new_state is ItemState.APROBADO:
            if not actor:
                raise InvalidTransition("aprobar requiere indicar quién aprueba")
            self.approved_by = actor
        self.state = new_state

    def add_objection(self, objection: Objection) -> None:
        self.objections.append(objection)


class Board(_Strict):
    """Tablero compartido del caso: ítems, hallazgos y mensajes entre agentes."""

    items: dict[str, BacklogItem] = Field(default_factory=dict)
    findings: list[Finding] = Field(default_factory=list)
    messages: list[AgentMessage] = Field(default_factory=list)

    def add_item(self, item: BacklogItem) -> None:
        if item.id in self.items:
            raise ValueError(f"ya existe un ítem con id {item.id}")
        if item.parent_id is not None and item.parent_id not in self.items:
            raise ValueError(f"el ítem padre no existe: {item.parent_id}")
        self.items[item.id] = item

    def add_finding(self, finding: Finding) -> None:
        if finding.item_id is not None and finding.item_id not in self.items:
            raise ValueError(f"el hallazgo apunta a un ítem inexistente: {finding.item_id}")
        self.findings.append(finding)

    def post_message(self, message: AgentMessage) -> None:
        self.messages.append(message)
