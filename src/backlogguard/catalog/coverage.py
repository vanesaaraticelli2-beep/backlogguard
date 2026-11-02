"""Matriz de cobertura: qué se vendió, qué se trató y qué quedó entre medio (fuera del curso).

La calcula el código, sin modelo, cruzando los compromisos de la preventa (Bloque 1B) con los requisitos del
catálogo (Bloque 2). El vínculo es `Draft.commitment_ids`, que queda guardado al leer cada reunión. El Auditor recibe
la matriz ya armada y solo juzga lo dudoso y redacta el hallazgo; las citas las sigue verificando `apply_report`.

Cada lista es un **candidato**, no un veredicto:
- `vendido_sin_requisito` → posible `vendido_no_tratado`. Solo se informa si ya hay reuniones leídas y requisitos
  aprobados; antes no hay con qué comparar y se avisa en lugar de acusar.
- `requisitos_sin_compromiso` → posible `tratado_no_vendido`. Sin filtros: un cambio de alcance se detecta justamente
  por lo que la preventa no tiene.
- `excluidos_con_requisito` → posible `cambio_de_alcance`: la propuesta decía que NO y ahora hay un requisito.
- `cobertura_perdida` → posible `decision_evolucionada`: el compromiso solo lo cubría una versión o un requisito
  que ya no está vigente.
Los supuestos y dependencias (`condicion`) se muestran aparte: no se «cubren» con una historia.
"""
from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field

from backlogguard.board import SourceType
from backlogguard.catalog.models import MEETING_TYPES, ProposalState, Requirement, RequirementStatus
from backlogguard.catalog.store import Catalog
from backlogguard.rag.compromisos import Baseline, Commitment
from backlogguard.rag.sources import SourceLibrary

TEXT_LIMIT = 200
EVIDENCE_PER_REQUIREMENT = 2


def _clip(text: str, limit: int = TEXT_LIMIT) -> str:
    return text if len(text) <= limit else text[: limit - 1] + "…"


@dataclass
class Coverage:
    meetings_read: int = 0
    active_requirements: int = 0
    pending_proposals: int = 0
    covered: list[dict] = field(default_factory=list)
    vendido_sin_requisito: list[dict] = field(default_factory=list)
    excluidos_con_requisito: list[dict] = field(default_factory=list)
    cobertura_perdida: list[dict] = field(default_factory=list)
    condiciones: list[dict] = field(default_factory=list)
    requisitos_sin_compromiso: list[dict] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "modo": "compromisos",
            "reuniones_leidas": self.meetings_read,
            "requisitos_activos": self.active_requirements,
            "propuestas_pendientes": self.pending_proposals,
            "avisos": self.warnings,
            "cubiertos": self.covered,
            "vendido_sin_requisito": self.vendido_sin_requisito,
            "excluidos_con_requisito": self.excluidos_con_requisito,
            "cobertura_perdida": self.cobertura_perdida,
            "condiciones": self.condiciones,
            "requisitos_sin_compromiso": self.requisitos_sin_compromiso,
        }


def _meeting_evidence(requirement: Requirement) -> list[dict]:
    meetings = [e for e in requirement.current.evidence if e.source_type in MEETING_TYPES]
    return [
        {"chunk_id": e.fragment_id, "reunion": e.source_name, "fecha": str(e.source_date), "cita": _clip(e.quote)}
        for e in meetings[:EVIDENCE_PER_REQUIREMENT]
    ]


def _requirement_ref(requirement: Requirement) -> dict:
    return {"id": requirement.id, "version": requirement.current.number, "titulo": requirement.current.draft.title}


def build_coverage(
    baseline: Baseline,
    catalog: Catalog,
    *,
    locate: Callable[[Commitment], str | None] | None = None,
) -> Coverage:
    """Cruza los compromisos con el catálogo. `locate` devuelve el fragmento de la preventa donde figura la cita."""
    requirements = catalog.requirements()
    active = [r for r in requirements if r.status is RequirementStatus.ACTIVO]
    coverage = Coverage(
        meetings_read=len(catalog.processed_sources()),
        active_requirements=len(active),
        pending_proposals=len(catalog.proposals(state=ProposalState.PENDIENTE)),
    )

    covering: dict[str, list[Requirement]] = {}
    for requirement in active:
        for cid in requirement.current.draft.commitment_ids:
            covering.setdefault(cid, []).append(requirement)
    # compromisos que alguna vez cubrió una versión anterior o un requisito que ya no está vigente
    past: dict[str, list[Requirement]] = {}
    for requirement in requirements:
        for version in requirement.versions:
            retired = requirement.status is not RequirementStatus.ACTIVO or version.number != requirement.current.number
            if retired:
                for cid in version.draft.commitment_ids:
                    past.setdefault(cid, []).append(requirement)

    can_compare = coverage.meetings_read > 0 and bool(active)
    if coverage.meetings_read == 0:
        coverage.warnings.append("Ninguna reunión fue leída todavía: no se informa «vendido y no tratado».")
    elif not active:
        coverage.warnings.append("No hay requisitos aprobados en el catálogo: no se informa «vendido y no tratado».")
    if coverage.pending_proposals:
        coverage.warnings.append(
            f"Hay {coverage.pending_proposals} propuestas sin decidir: parte de lo tratado puede no figurar todavía."
        )

    for commitment in baseline.commitments:
        row = {"id": commitment.id, "epica": commitment.epic, "capacidad": _clip(commitment.capability), "alcance": commitment.scope}
        covers = covering.get(commitment.id, [])
        # lo que el Auditor necesita para citar; solo va donde puede haber hallazgo
        detail = {
            **row,
            "pagina": commitment.page,
            "chunk_id": locate(commitment) if locate else None,
            "cita": _clip(commitment.quote),
        }
        if commitment.scope == "condicion":
            coverage.condiciones.append({**row, "requisitos": [r.id for r in covers]})
        elif commitment.scope == "excluido":
            if covers:
                coverage.excluidos_con_requisito.append(
                    {**detail, "requisitos": [{**_requirement_ref(r), "evidencia": _meeting_evidence(r)} for r in covers]}
                )
            else:
                coverage.covered.append({**row, "requisitos": []})
        elif covers:
            coverage.covered.append({**row, "requisitos": [r.id for r in covers]})
        elif commitment.id in past:
            coverage.cobertura_perdida.append(
                {**detail, "antes": [{**_requirement_ref(r), "estado": r.status.value} for r in past[commitment.id]]}
            )
        elif can_compare:
            coverage.vendido_sin_requisito.append(detail)

    # Sin filtros: lo que no figura en la preventa es justo lo que delata un cambio de alcance.
    for requirement in active:
        if not requirement.current.draft.commitment_ids:
            coverage.requisitos_sin_compromiso.append({**_requirement_ref(requirement), "evidencia": _meeting_evidence(requirement)})
    return coverage


def current_baseline(library: SourceLibrary, store) -> Baseline | None:
    """Compromisos vigentes de la única preventa de la biblioteca; `None` si no hay una sola o no se extrajeron."""
    presales = [document_id for document_id, meta in library.describe() if meta.source_type is SourceType.PREVENTA]
    if len(presales) != 1:
        return None
    baseline = store.current(library.load(presales[0]))
    return baseline if baseline is not None and baseline.commitments else None
