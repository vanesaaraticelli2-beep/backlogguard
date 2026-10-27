"""Revisión humana de las propuestas de una reunión (fuera del curso).

Quién decide y qué entra en un lote lo fija el código, no el modelo:
- Un lote solo admite propuestas «nuevo» o «refina», pendientes y de una reunión en orden.
- Contradicciones, divisiones, fusiones e inciertos (y todo lo de una reunión fuera de orden) se deciden una por una.
- Un cambio de alcance (contradice) lo decide el service manager; el resto, el product owner.
Quien decide queda registrado por su rol, no por su nombre.
"""
from __future__ import annotations

from dataclasses import dataclass, field

from backlogguard.catalog.models import Proposal, ProposalKind, ProposalState
from backlogguard.catalog.store import Catalog, CatalogError

PRODUCT_OWNER = "product_owner"
SERVICE_MANAGER = "service_manager"
BATCH_KINDS = {ProposalKind.NUEVO, ProposalKind.REFINA}


def decider_role(proposal: Proposal) -> str:
    return SERVICE_MANAGER if proposal.kind is ProposalKind.CONTRADICE else PRODUCT_OWNER


def batchable(proposal: Proposal) -> bool:
    return proposal.state is ProposalState.PENDIENTE and proposal.kind in BATCH_KINDS and not proposal.needs_human_alone


def pending_batch(catalog: Catalog, source_id: str) -> list[Proposal]:
    return [p for p in catalog.proposals(state=ProposalState.PENDIENTE, source_id=source_id) if batchable(p)]


def pending_individual(catalog: Catalog, source_id: str) -> list[Proposal]:
    return [p for p in catalog.proposals(state=ProposalState.PENDIENTE, source_id=source_id) if not batchable(p)]


@dataclass
class ReviewResult:
    applied: list[Proposal] = field(default_factory=list)
    rejected: list[Proposal] = field(default_factory=list)


def decide_one(catalog: Catalog, proposal_id: str, *, approve: bool, role: str, note: str = "") -> Proposal:
    """Decide una propuesta. Si se aprueba, se aplica en el acto: crea o versiona el requisito."""
    proposal = catalog.proposal(proposal_id)
    if proposal.kind is ProposalKind.INCIERTO and approve:
        raise CatalogError("Un incierto no se aprueba tal cual: reclasificalo como nuevo, refina o cubierto, o descartalo.")
    if role != decider_role(proposal):
        raise CatalogError(f"{proposal_id} lo decide el rol «{decider_role(proposal)}», no «{role}».")
    decided = catalog.decide(proposal_id, approve=approve, by=role, note=note)
    return catalog.apply(proposal_id) if approve else decided


def decide_batch(catalog: Catalog, proposal_ids: list[str], *, approve: bool, role: str, note: str = "") -> ReviewResult:
    """Decide varias propuestas a la vez. Falla entera, sin cambiar nada, si alguna no admite lote o no corresponde al rol."""
    proposals = [catalog.proposal(i) for i in proposal_ids]
    for p in proposals:
        if not batchable(p):
            raise CatalogError(f"{p.id} no admite aprobación por lote: se decide una por una.")
        if role != decider_role(p):
            raise CatalogError(f"{p.id} lo decide el rol «{decider_role(p)}», no «{role}».")
    result = ReviewResult()
    for p in proposals:
        (result.applied if approve else result.rejected).append(decide_one(catalog, p.id, approve=approve, role=role, note=note))
    return result
