"""Convierte lo que dejó una corrida (tablero, catálogo, fuentes) en una `Salida` evaluable."""
from __future__ import annotations

from backlogguard.board import Board, ItemKind
from backlogguard.catalog import Catalog, ProposalKind, ProposalState, RequirementStatus
from backlogguard.evaluation.scoring import Cita, Elemento, Salida
from backlogguard.evaluation.truth import normalizar
from backlogguard.rag import SourceLibrary


def fuentes_de(library: SourceLibrary) -> dict[str, str]:
    """Texto de cada fuente, por su nombre normalizado: contra eso se verifican las citas."""
    return {normalizar(meta.source_name): library.load(document_id).text for document_id, meta in library.describe()}


def _citas(citations) -> list[Cita]:
    return [Cita(quote=c.quote, source_name=c.source_name) for c in citations]


def salida_desde_estado(nombre: str, state: dict, catalog: Catalog | None = None, *, segundos: float = 0.0) -> Salida:
    """Requisitos = los activos del catálogo si lo hay (flujo con documentos propios) y, si no, las historias del tablero."""
    board = Board.model_validate(state["board"])
    requisitos: list[Elemento] = []
    activos = catalog.requirements(RequirementStatus.ACTIVO) if catalog is not None else []
    if activos:
        for req in activos:
            draft = req.current.draft
            texto = " ".join([draft.title, draft.description, *draft.acceptance_criteria])
            requisitos.append(Elemento(req.id, texto, _citas(req.current.evidence)))
    else:
        for item in board.items.values():
            if item.kind is ItemKind.HISTORIA:
                texto = " ".join([item.title, item.description, *item.acceptance_criteria])
                requisitos.append(Elemento(item.id, texto, _citas(item.citations)))
    hallazgos = [Elemento(f.id, f.description, _citas(f.citations), f.kind.value) for f in board.findings]
    errores = [f"{e.get('node')}: {str(e.get('error', ''))[:160]}" for e in state.get("errors", [])]
    return Salida(nombre, requisitos, hallazgos, tokens=int(state.get("tokens", 0)), segundos=segundos, errores=errores)


def salida_desde_catalogo(nombre: str, catalog: Catalog, state: dict | None = None, *, propuestas: bool = False) -> Salida:
    """El flujo con documentos propios, medido en el catálogo (fuera del curso).

    - `propuestas=True`: lo que propuso el sistema al leer las reuniones, ANTES de que decida una persona (incluye lo que
      después se rechazó). Mide a los agentes solos.
    - `propuestas=False`: los requisitos que quedaron aprobados. Mide al sistema con la persona en el circuito.

    Hallazgos: las contradicciones que detectó la lectura de reuniones (propuestas «contradice») y los del Auditor en la corrida.
    """
    todas = catalog.proposals()
    requisitos: list[Elemento] = []
    if propuestas:
        for p in todas:
            if p.kind in (ProposalKind.NUEVO, ProposalKind.REFINA, ProposalKind.INCIERTO, ProposalKind.DIVIDE, ProposalKind.FUSIONA) and p.drafts:
                texto = " ".join(t for d in p.drafts for t in (d.title, d.description, *d.acceptance_criteria))
                requisitos.append(Elemento(p.id, texto, _citas(p.evidence)))
    else:
        for req in catalog.requirements(RequirementStatus.ACTIVO):
            draft = req.current.draft
            requisitos.append(Elemento(req.id, " ".join([draft.title, draft.description, *draft.acceptance_criteria]), _citas(req.current.evidence)))
    hallazgos = [
        Elemento(p.id, " ".join([p.rationale or "", *(d.title for d in p.drafts), *(e.quote for e in p.evidence)]), _citas(p.evidence), "contradiccion")
        for p in todas
        if p.kind is ProposalKind.CONTRADICE and (propuestas or p.state is ProposalState.APLICADA)
    ]
    tokens, errores = 0, []
    if state:
        board = Board.model_validate(state["board"])
        hallazgos += [Elemento(f.id, f.description, _citas(f.citations), f.kind.value) for f in board.findings]
        tokens = int(state.get("tokens", 0))
        errores = [f"{e.get('node')}: {str(e.get('error', ''))[:160]}" for e in state.get("errors", [])]
    return Salida(nombre, requisitos, hallazgos, tokens=tokens, errores=errores)
