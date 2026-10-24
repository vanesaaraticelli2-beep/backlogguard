"""Tools del Agente de Requerimientos: ingestar, buscar y redactar.

Los handlers son métodos de `RequirementsToolkit`, que recibe lo que necesitan (biblioteca
de fuentes, retriever y tablero) en vez de usar estado global. Las citas se construyen con
la metadata del fragmento indexado: el modelo solo indica `chunk_id` y la frase citada, y
no puede inventar fecha, reunión ni orador.
"""
from __future__ import annotations

import hashlib
import json
import re
from typing import Annotated

from pydantic import BaseModel, ConfigDict, Field, StringConstraints, field_validator

from backlogguard.board import BacklogItem, Board, Citation, ItemKind, SourceType
from backlogguard.rag import SourceLibrary, SourceNotFound, build_chunks
from backlogguard.rag.retrieval import InMemoryRetriever, QdrantRetriever
from backlogguard.tools.models import ToolResult

_GHERKIN = re.compile(r"\b(dado|given)\b.*\b(cuando|when)\b.*\b(entonces|then)\b", re.IGNORECASE | re.DOTALL)
_ID_PREFIX = {
    ItemKind.EPICA: "EP",
    ItemKind.HISTORIA: "HU",
    ItemKind.TAREA: "TA",
    ItemKind.CASO_DE_PRUEBA: "CP",
}

DocumentId = Annotated[str, StringConstraints(pattern=r"^[a-z0-9_-]{1,60}$")]


class _Args(BaseModel):
    model_config = ConfigDict(extra="forbid")


class IngestArgs(_Args):
    document_id: DocumentId = Field(description="Nombre de la fuente en la biblioteca (sin extensión)")


class SearchArgs(_Args):
    query: str = Field(min_length=3, max_length=300)
    top_k: int = Field(default=5, ge=1, le=8)
    source_type: SourceType | None = None
    document_id: DocumentId | None = None


class CitationRef(_Args):
    chunk_id: str = Field(min_length=1, description="chunk_id devuelto por buscar_en_fuentes")
    quote: str = Field(min_length=3, description="Frase textual del fragmento que sustenta el ítem")


class DraftArgs(_Args):
    kind: ItemKind
    title: str = Field(min_length=3, max_length=140)
    description: str = Field(default="", max_length=1200)
    acceptance_criteria: list[str] = Field(
        default_factory=list, description="Escenarios Gherkin: Dado ... Cuando ... Entonces ..."
    )
    citations: list[CitationRef] = Field(min_length=1)

    @field_validator("acceptance_criteria")
    @classmethod
    def _gherkin(cls, criteria: list[str]) -> list[str]:
        for criterion in criteria:
            if not _GHERKIN.search(criterion):
                raise ValueError(f"el criterio no es Gherkin (Dado/Cuando/Entonces): {criterion[:60]!r}")
        return criteria

    @field_validator("title")
    @classmethod
    def _title(cls, value: str) -> str:
        return " ".join(value.split())


def _fail(content: str, error_type: str) -> ToolResult:
    return ToolResult(ok=False, content=content, metadata={"error_type": error_type})


class RequirementsToolkit:
    def __init__(
        self,
        library: SourceLibrary,
        retriever: InMemoryRetriever | QdrantRetriever,
        board: Board,
    ):
        self.library = library
        self.retriever = retriever
        self.board = board

    def ingestar_y_fragmentar(self, args: dict) -> ToolResult:
        try:
            document = self.library.load(args["document_id"])
        except SourceNotFound as exc:
            return _fail(str(exc), "source_not_found")
        metadata = json.loads(document.metadata.model_dump_json())
        chunks = build_chunks(document.document_id, document.text, metadata)
        self.retriever.index(chunks)
        return ToolResult(
            ok=True,
            content=f"Fuente {document.document_id} indexada en {len(chunks)} fragmentos.",
            metadata={"document_id": document.document_id, "chunks": len(chunks)},
        )

    def buscar_en_fuentes(self, args: dict) -> ToolResult:
        filters = {}
        if args.get("source_type"):
            filters["source_type"] = args["source_type"].value if hasattr(args["source_type"], "value") else args["source_type"]
        if args.get("document_id"):
            filters["document_id"] = args["document_id"]
        results = self.retriever.search(args["query"], top_k=args["top_k"], filters=filters or None)
        fragments = [
            {
                "chunk_id": r.chunk_id,
                "texto": r.text,
                "reunion": r.metadata.get("source_name"),
                "tipo": r.metadata.get("source_type"),
                "fecha": r.metadata.get("source_date"),
                "orador": r.metadata.get("speaker"),
                "score": round(r.score, 3),
            }
            for r in results
        ]
        return ToolResult(
            ok=True,
            content=json.dumps(fragments, ensure_ascii=False),
            metadata={"results": len(fragments)},
        )

    def redactar_historia(self, args: dict) -> ToolResult:
        citations = []
        for ref in args["citations"]:
            fragment = self.retriever.get(ref["chunk_id"])
            if fragment is None:
                return _fail(f"La cita apunta a un fragmento inexistente: {ref['chunk_id']}", "unknown_chunk")
            citations.append(
                Citation(
                    fragment_id=fragment.chunk_id,
                    quote=ref["quote"],
                    source_name=fragment.metadata["source_name"],
                    source_type=fragment.metadata["source_type"],
                    source_date=fragment.metadata["source_date"],
                    speaker=fragment.metadata.get("speaker"),
                )
            )
        kind = ItemKind(args["kind"])
        digest = hashlib.sha1(f"{kind.value}|{' '.join(args['title'].lower().split())}".encode()).hexdigest()[:8]
        item_id = f"{_ID_PREFIX[kind]}-{digest}"
        if item_id in self.board.items:
            return _fail(f"Ya existe un ítem con ese tipo y título: {item_id}", "duplicate_item")
        self.board.add_item(
            BacklogItem(
                id=item_id,
                kind=kind,
                title=args["title"],
                description=args.get("description", ""),
                acceptance_criteria=args.get("acceptance_criteria", []),
                citations=citations,
            )
        )
        return ToolResult(ok=True, content=f"Ítem {item_id} creado en borrador.", metadata={"item_id": item_id})

    def implementations(self) -> dict:
        """(handler, args_model, idempotent) por nombre de tool, para el catálogo."""
        return {
            "ingestar_y_fragmentar": (self.ingestar_y_fragmentar, IngestArgs, True),
            "buscar_en_fuentes": (self.buscar_en_fuentes, SearchArgs, True),
            "redactar_historia": (self.redactar_historia, DraftArgs, False),
        }
