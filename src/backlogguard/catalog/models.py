"""Modelos del catálogo persistente de requisitos (fuera del curso).

Un requisito tiene una identidad estable (`RQ-nnn`) que no depende de su título, versiones que se encadenan con una
relación explícita y evidencias citadas. Los cambios llegan como propuestas que una persona aprueba.
"""
from __future__ import annotations

from enum import StrEnum

from pydantic import BaseModel, ConfigDict, Field, model_validator

from backlogguard.board import Citation, SourceType

MEETING_TYPES = {SourceType.REUNION, SourceType.MINUTA}


class _Strict(BaseModel):
    model_config = ConfigDict(extra="forbid")


class Relation(StrEnum):
    """Cómo se relaciona una versión con lo anterior."""

    NUEVO = "nuevo"
    REFINA = "refina"
    REEMPLAZA = "reemplaza"
    DIVIDE = "divide"
    FUSIONA = "fusiona"


class RequirementStatus(StrEnum):
    ACTIVO = "activo"
    REEMPLAZADO = "reemplazado"
    DIVIDIDO = "dividido"
    FUSIONADO = "fusionado"


class ProposalKind(StrEnum):
    NUEVO = "nuevo"
    REFINA = "refina"
    CUBIERTO = "cubierto"
    CONTRADICE = "contradice"
    DIVIDE = "divide"
    FUSIONA = "fusiona"
    INCIERTO = "incierto"


class ProposalState(StrEnum):
    PENDIENTE = "pendiente"
    APROBADA = "aprobada"
    RECHAZADA = "rechazada"
    APLICADA = "aplicada"


class EvidenceRole(StrEnum):
    ORIGEN = "origen"  # sostiene el requisito
    REFUERZO = "refuerzo"  # otra reunión que lo vuelve a pedir (ya cubierto)
    CONTRADICE = "contradice"


class Evidence(Citation):
    """Cita verificada, ligada a la fuente y a la huella con la que se leyó."""

    source_id: str = Field(min_length=1)
    source_fingerprint: str = Field(min_length=1)
    role: EvidenceRole = EvidenceRole.ORIGEN

    @property
    def key(self) -> str:
        return f"{self.source_fingerprint}|{self.fragment_id}|{' '.join(self.quote.casefold().split())}"


class Draft(_Strict):
    """Contenido de una versión de requisito."""

    title: str = Field(min_length=3, max_length=200)
    description: str = ""
    acceptance_criteria: list[str] = Field(default_factory=list)
    commitment_ids: list[str] = Field(default_factory=list, description="Compromisos de la preventa que cubre (C-nnn)")


class Version(_Strict):
    requirement_id: str
    number: int = Field(ge=1)
    relation: Relation
    draft: Draft
    parents: list[str] = Field(default_factory=list, description="Requisitos de los que sale (divide, fusiona)")
    proposal_id: str | None = None
    approved_by: str
    created_at: str
    current: bool = True
    evidence: list[Evidence] = Field(default_factory=list)


class Requirement(_Strict):
    id: str
    status: RequirementStatus
    replaced_by: list[str] = Field(default_factory=list)
    current: Version
    versions: list[Version]
    conflicts: list[Evidence] = Field(default_factory=list)


NEEDS_MEETING_EVIDENCE = {ProposalKind.NUEVO, ProposalKind.REFINA, ProposalKind.DIVIDE, ProposalKind.FUSIONA}
ALWAYS_HUMAN = {ProposalKind.CONTRADICE, ProposalKind.DIVIDE, ProposalKind.FUSIONA, ProposalKind.INCIERTO}


class Proposal(_Strict):
    id: str = ""
    source_id: str = Field(min_length=1)
    fingerprint: str = Field(min_length=1)
    candidate_key: str = Field(min_length=1, description="Identifica al candidato dentro de la fuente (idempotencia)")
    kind: ProposalKind
    targets: list[str] = Field(default_factory=list)
    drafts: list[Draft] = Field(default_factory=list)
    evidence: list[Evidence] = Field(default_factory=list)
    rationale: str = ""
    state: ProposalState = ProposalState.PENDIENTE
    decided_by: str | None = None
    note: str = ""
    created_at: str = ""
    affected: list[str] = Field(default_factory=list, description="Requisitos que quedaron creados o cambiados al aplicarla")
    confidence: float | None = Field(default=None, ge=0, le=1, description="Confianza del clasificador, si lo hubo")
    out_of_order: bool = Field(default=False, description="La reunión es anterior a otra ya procesada: se revisa a mano")

    @property
    def needs_human_alone(self) -> bool:
        """Contradicciones, divisiones, fusiones e inciertos nunca entran a una aprobación automática por lote."""
        return self.kind in ALWAYS_HUMAN or self.out_of_order

    @model_validator(mode="after")
    def _coherent(self) -> "Proposal":
        k, t, d = self.kind, len(self.targets), len(self.drafts)
        shape = {
            ProposalKind.NUEVO: (t == 0 and d == 1, "nuevo: sin destino y con un borrador"),
            ProposalKind.REFINA: (t == 1 and d == 1, "refina: un requisito destino y un borrador"),
            ProposalKind.CUBIERTO: (t == 1 and d == 0, "cubierto: un requisito destino y sin borrador"),
            ProposalKind.CONTRADICE: (t == 1 and d <= 1, "contradice: un requisito destino y, si lo reemplaza, un borrador"),
            ProposalKind.DIVIDE: (t == 1 and d >= 2, "divide: un requisito destino y al menos dos borradores"),
            ProposalKind.FUSIONA: (t >= 2 and d == 1, "fusiona: al menos dos destinos y un borrador"),
            ProposalKind.INCIERTO: (True, ""),
        }[k]
        if not shape[0]:
            raise ValueError(shape[1])
        needs_meeting = k in NEEDS_MEETING_EVIDENCE or (k is ProposalKind.CONTRADICE and d == 1)
        if needs_meeting and not any(e.source_type in MEETING_TYPES for e in self.evidence):
            raise ValueError("la preventa no alcanza como única evidencia: falta una cita de reunión o minuta")
        if k is ProposalKind.CUBIERTO and not self.evidence:
            raise ValueError("cubierto: hace falta al menos una evidencia")
        return self
