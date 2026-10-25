"""Tools del Crítico: verificar citas, buscar contraevidencia y evaluar DoR/INVEST.

Son de solo lectura y cálculo: el Crítico no escribe en el tablero (lo impide `ToolPolicy`).
La verificación de citas es determinística; el juicio de sustento lo emite el modelo.
"""
from __future__ import annotations

import json
import re
from dataclasses import dataclass

from pydantic import BaseModel, ConfigDict, Field

from backlogguard.board import BacklogItem, Board, ItemKind
from backlogguard.board.similarity import similar_titles
from backlogguard.rag.retrieval import InMemoryRetriever, QdrantRetriever
from backlogguard.tools.models import ToolResult

MAX_CRITERIA = 5
_STORY = re.compile(r"\bcomo\b.*\bquiero\b.*\bpara\b", re.IGNORECASE | re.DOTALL)
_GHERKIN = re.compile(r"\b(dado|given)\b.*\b(cuando|when)\b.*\b(entonces|then)\b", re.IGNORECASE | re.DOTALL)
_QUOTES = str.maketrans({"“": '"', "”": '"', "«": '"', "»": '"', "‘": "'", "’": "'"})


class _Args(BaseModel):
    model_config = ConfigDict(extra="forbid")


class ItemArgs(_Args):
    item_id: str = Field(min_length=1, max_length=60)


class CounterEvidenceArgs(_Args):
    item_id: str = Field(min_length=1, max_length=60)
    query: str | None = Field(default=None, min_length=3, max_length=300)
    top_k: int = Field(default=5, ge=1, le=8)


def _normalize_quote(text: str) -> str:
    """Ignora espacios, mayúsculas y comillas tipográficas; conserva acentos y palabras."""
    return " ".join(text.translate(_QUOTES).casefold().split())


def quote_matches(quote: str, text: str) -> bool:
    """¿La frase figura textualmente en el texto? (mismo criterio que `verificar_cita`)."""
    return _normalize_quote(quote) in _normalize_quote(text)


@dataclass(frozen=True)
class CitationCheck:
    fragment_id: str
    ok: bool
    reason: str


def check_citations(item: BacklogItem, retriever: InMemoryRetriever | QdrantRetriever) -> list[CitationCheck]:
    """Verifica cada cita contra el fragmento indexado. No usa ningún modelo."""
    checks = []
    for citation in item.citations:
        fragment = retriever.get(citation.fragment_id)
        if fragment is None:
            checks.append(CitationCheck(citation.fragment_id, False, "el fragmento no existe en las fuentes"))
        elif not quote_matches(citation.quote, fragment.text):
            checks.append(CitationCheck(citation.fragment_id, False, "la frase citada no figura textualmente en el fragmento"))
        elif (
            fragment.metadata.get("source_name") != citation.source_name
            or str(fragment.metadata.get("source_date")) != citation.source_date.isoformat()
        ):
            checks.append(CitationCheck(citation.fragment_id, False, "la reunión o la fecha no coinciden con la fuente"))
        else:
            checks.append(CitationCheck(citation.fragment_id, True, "cita textual verificada"))
    return checks


def _fail(content: str, error_type: str) -> ToolResult:
    return ToolResult(ok=False, content=content, metadata={"error_type": error_type})


class CriticToolkit:
    def __init__(self, retriever: InMemoryRetriever | QdrantRetriever, board: Board):
        self.retriever = retriever
        self.board = board

    def _item(self, item_id: str) -> BacklogItem | None:
        return self.board.items.get(item_id)

    def verificar_cita(self, args: dict) -> ToolResult:
        item = self._item(args["item_id"])
        if item is None:
            return _fail(f"No existe el ítem {args['item_id']}", "unknown_item")
        checks = check_citations(item, self.retriever)
        return ToolResult(
            ok=True,
            content=json.dumps(
                [{"fragment_id": c.fragment_id, "ok": c.ok, "detalle": c.reason} for c in checks],
                ensure_ascii=False,
            ),
            metadata={"all_ok": all(c.ok for c in checks)},
        )

    def buscar_contraevidencia(self, args: dict) -> ToolResult:
        item = self._item(args["item_id"])
        if item is None:
            return _fail(f"No existe el ítem {args['item_id']}", "unknown_item")
        own = {citation.fragment_id for citation in item.citations}
        cited_on = max(citation.source_date for citation in item.citations) if item.citations else None
        query = args.get("query") or f"{item.title}. {item.description}"
        found = self.retriever.hybrid_search(query, top_k=args["top_k"] + len(own))
        fragments = [
            {
                "chunk_id": r.chunk_id,
                "texto": r.text,
                "reunion": r.metadata.get("source_name"),
                "tipo": r.metadata.get("source_type"),
                "fecha": r.metadata.get("source_date"),
                "orador": r.metadata.get("speaker"),
                "pagina": r.page,
                "mas_reciente_que_la_cita": bool(cited_on and str(r.metadata.get("source_date")) > cited_on.isoformat()),
                "score": round(r.score, 3),
            }
            for r in found
            if r.chunk_id not in own
        ][: args["top_k"]]
        return ToolResult(ok=True, content=json.dumps(fragments, ensure_ascii=False), metadata={"results": len(fragments)})

    def evaluar_dor_invest(self, args: dict) -> ToolResult:
        item = self._item(args["item_id"])
        if item is None:
            return _fail(f"No existe el ítem {args['item_id']}", "unknown_item")
        needs_gherkin = item.kind in (ItemKind.HISTORIA, ItemKind.CASO_DE_PRUEBA)
        duplicates = [
            other.id
            for other in self.board.items.values()
            if other.id != item.id and other.kind is item.kind and similar_titles(item.title, other.title)
        ]
        checks = [
            ("tiene_citas", bool(item.citations), f"{len(item.citations)} cita(s)"),
            (
                "formato_como_quiero_para",
                item.kind is not ItemKind.HISTORIA or bool(_STORY.search(item.description)),
                "la descripción de una historia debe decir Como … quiero … para …",
            ),
            (
                "criterios_gherkin",
                not needs_gherkin
                or (bool(item.acceptance_criteria) and all(_GHERKIN.search(c) for c in item.acceptance_criteria)),
                "se esperan escenarios Dado/Cuando/Entonces",
            ),
            (
                "tamano_acotado",
                len(item.acceptance_criteria) <= MAX_CRITERIA,
                f"{len(item.acceptance_criteria)} criterio(s); máximo {MAX_CRITERIA}",
            ),
            ("sin_duplicados", not duplicates, f"posible duplicado de {duplicates}" if duplicates else "sin duplicados"),
        ]
        report = {
            "item": {
                "id": item.id,
                "tipo": item.kind.value,
                "estado": item.state.value,
                "titulo": item.title,
                "descripcion": item.description,
                "criterios": item.acceptance_criteria,
                "citas": [
                    {"fragment_id": c.fragment_id, "frase": c.quote, "reunion": c.source_name, "fecha": c.source_date.isoformat()}
                    for c in item.citations
                ],
                "objeciones_previas": [o.text for o in item.objections],
            },
            "controles": [{"nombre": name, "ok": ok, "detalle": detail} for name, ok, detail in checks],
        }
        return ToolResult(
            ok=True,
            content=json.dumps(report, ensure_ascii=False),
            metadata={"dor_ok": all(ok for _, ok, _ in checks)},
        )

    def implementations(self) -> dict:
        return {
            "verificar_cita": (self.verificar_cita, ItemArgs, True),
            "buscar_contraevidencia": (self.buscar_contraevidencia, CounterEvidenceArgs, True),
            "evaluar_dor_invest": (self.evaluar_dor_invest, ItemArgs, True),
        }
