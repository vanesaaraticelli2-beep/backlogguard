"""Informe del Auditor y su aplicación al tablero.

El Auditor no escribe hallazgos: devuelve un `AuditReport` y este módulo, que es código,
verifica cada cita, decide a quién va dirigido cada hallazgo y reabre los ítems que el
productor debe corregir. Fuera del curso.
"""
from __future__ import annotations

import hashlib
from dataclasses import dataclass, field

from pydantic import BaseModel, ConfigDict, Field

from backlogguard.agents.structured import extract_json
from backlogguard.board import AgentRole, Board, Citation, Finding, FindingKind, ItemState, Objection
from backlogguard.rag.retrieval import InMemoryRetriever, QdrantRetriever
from backlogguard.tools.critico import quote_matches
from backlogguard.tools.requerimientos import CitationRef


class FindingDraft(BaseModel):
    model_config = ConfigDict(extra="forbid")

    kind: FindingKind
    description: str = Field(min_length=10, max_length=600)
    item_id: str | None = Field(default=None, description="Solo si un ítem del tablero quedó desactualizado")
    citations: list[CitationRef] = Field(min_length=1)


class AuditReport(BaseModel):
    model_config = ConfigDict(extra="forbid")

    findings: list[FindingDraft] = Field(default_factory=list)
    summary: str = ""


def parse_report(text: str) -> AuditReport:
    return AuditReport.model_validate_json(extract_json(text))


@dataclass
class ApplyResult:
    applied: list[Finding] = field(default_factory=list)
    discarded: list[tuple[FindingDraft, str]] = field(default_factory=list)


# Estados en los que un ítem aún puede reabrirse para que el productor lo corrija.
REOPENABLE = (ItemState.BORRADOR, ItemState.SUSTENTADO, ItemState.OBJETADO)


def finding_id(draft: FindingDraft) -> str:
    digest = hashlib.sha1(f"{draft.kind.value}|{' '.join(draft.description.lower().split())}".encode()).hexdigest()[:8]
    return f"F-{digest}"


def apply_report(
    report: AuditReport,
    board: Board,
    retriever: InMemoryRetriever | QdrantRetriever,
) -> ApplyResult:
    """Convierte el informe en hallazgos del tablero. Descarta los que no se pueden verificar."""
    result = ApplyResult()
    known = {finding.id for finding in board.findings}

    for draft in report.findings:
        if draft.item_id is not None and draft.item_id not in board.items:
            result.discarded.append((draft, f"el ítem {draft.item_id} no existe"))
            continue
        citations, problem = _build_citations(draft, retriever)
        if problem:
            result.discarded.append((draft, problem))
            continue
        fid = finding_id(draft)
        if fid in known:
            result.discarded.append((draft, "hallazgo ya registrado"))
            continue

        item = board.items.get(draft.item_id) if draft.item_id else None
        for_producer = (
            draft.kind is FindingKind.DECISION_EVOLUCIONADA and item is not None and item.state in REOPENABLE
        )
        finding = Finding(
            id=fid,
            kind=draft.kind,
            raised_by=AgentRole.AUDITOR,
            addressee=AgentRole.REQUERIMIENTOS if for_producer else AgentRole.SUPERVISOR,
            description=draft.description,
            item_id=draft.item_id,
            citations=citations,
        )
        board.add_finding(finding)
        known.add(fid)
        result.applied.append(finding)

        if for_producer:
            if item.state is ItemState.SUSTENTADO or item.state is ItemState.BORRADOR:
                item.transition_to(ItemState.OBJETADO)
            item.add_objection(
                Objection(
                    id=f"{item.id}-A{len(item.objections) + 1}",
                    raised_by=AgentRole.AUDITOR,
                    text=draft.description,
                    round=1,
                )
            )
    return result


def _build_citations(
    draft: FindingDraft, retriever: InMemoryRetriever | QdrantRetriever
) -> tuple[list[Citation], str | None]:
    citations = []
    for ref in draft.citations:
        fragment = retriever.get(ref.chunk_id)
        if fragment is None:
            return [], f"la cita apunta a un fragmento inexistente: {ref.chunk_id}"
        if not quote_matches(ref.quote, fragment.text):
            return [], f"cita no verificable en {ref.chunk_id}"
        citations.append(
            Citation(
                fragment_id=fragment.chunk_id,
                quote=ref.quote,
                source_name=fragment.metadata["source_name"],
                source_type=fragment.metadata["source_type"],
                source_date=fragment.metadata["source_date"],
                speaker=fragment.metadata.get("speaker"),
                page=fragment.page,
            )
        )
    return citations, None
