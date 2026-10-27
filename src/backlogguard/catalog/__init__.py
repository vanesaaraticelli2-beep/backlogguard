"""Catálogo persistente de requisitos: identidad estable, versiones, evidencias y propuestas aprobadas por personas."""
from backlogguard.catalog.models import (
    Draft,
    Evidence,
    EvidenceRole,
    Proposal,
    ProposalKind,
    ProposalState,
    Relation,
    Requirement,
    RequirementStatus,
    Version,
)
from backlogguard.catalog.store import Catalog, CatalogError

__all__ = [
    "Catalog",
    "CatalogError",
    "Draft",
    "Evidence",
    "EvidenceRole",
    "Proposal",
    "ProposalKind",
    "ProposalState",
    "Relation",
    "Requirement",
    "RequirementStatus",
    "Version",
]
