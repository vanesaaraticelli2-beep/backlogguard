"""Tools del Auditor: comparar con la preventa, detectar contradicciones y custodiar la memoria.

Las tools de consulta reúnen **evidencia** (fragmentos, fechas, oradores, similitud); la
clasificación (cobertura, evolución o contradicción) la hace el modelo. Con embeddings léxicos
la similitud es una ayuda para ordenar, no un veredicto: por eso no se usan umbrales para decidir.
"""
from __future__ import annotations

import json
from datetime import date

from pydantic import BaseModel, ConfigDict, Field

from backlogguard.board import Board
from backlogguard.memory import ProjectMemory
from backlogguard.rag.retrieval import InMemoryRetriever, QdrantRetriever, SearchResult
from backlogguard.tools.critico import quote_matches
from backlogguard.tools.models import ExecutionContext, ToolResult

MEETING_TYPES = ("reunion", "minuta")


class _Args(BaseModel):
    model_config = ConfigDict(extra="forbid")


class CompareArgs(_Args):
    matches_per_point: int = Field(default=3, ge=1, le=5)


class ContradictionArgs(_Args):
    top_pairs: int = Field(default=10, ge=1, le=20)
    min_score: float = Field(default=0.3, ge=0.0, le=1.0)


class DecisionsArgs(_Args):
    query: str | None = Field(default=None, min_length=2, max_length=200)


class RegisterDecisionArgs(_Args):
    key: str = Field(min_length=3, max_length=80, description="Identificador estable de la decisión")
    decision: str = Field(min_length=3, max_length=400)
    fragment_id: str = Field(min_length=1, description="chunk_id del fragmento donde se decidió")
    quote: str = Field(min_length=3, description="Frase textual del fragmento")
    authority: str = Field(min_length=2, max_length=60, description="Quién tenía autoridad (Cliente, PO…)")
    supersedes: str | None = Field(default=None, description="id de la decisión vigente que reemplaza")


def _fragment(result: SearchResult, *, with_text: bool = True) -> dict:
    data = {
        "chunk_id": result.chunk_id,
        "reunion": result.metadata.get("source_name"),
        "fecha": result.metadata.get("source_date"),
        "orador": result.metadata.get("speaker"),
    }
    if with_text:
        data["texto"] = result.text
    return data


def _fail(content: str, error_type: str) -> ToolResult:
    return ToolResult(ok=False, content=content, metadata={"error_type": error_type})


class AuditorToolkit:
    def __init__(
        self,
        retriever: InMemoryRetriever | QdrantRetriever,
        board: Board,
        memory: ProjectMemory,
        context: ExecutionContext,
    ):
        self.retriever = retriever
        self.board = board
        self.memory = memory
        self.context = context

    def comparar_con_preventa(self, args: dict) -> ToolResult:
        chunks = self.retriever.all_chunks()
        selling = [c for c in chunks if c.metadata.get("source_type") == "preventa"]
        meetings = [c for c in chunks if c.metadata.get("source_type") in MEETING_TYPES]
        if not selling:
            return _fail("No hay fuentes de preventa indexadas.", "no_presale")

        def best(text: str, pool: list[SearchResult], top: int) -> list[dict]:
            ids = {c.chunk_id for c in pool}
            ranked = self.retriever.search(text, top_k=len(chunks))
            return [
                {"chunk_id": r.chunk_id, "score": round(r.score, 3)}
                for r in ranked
                if r.chunk_id in ids
            ][:top]

        report = {
            "items": [
                {
                    "id": item.id,
                    "titulo": item.title,
                    "estado": item.state.value,
                    "citas": [c.fragment_id for c in item.citations],
                }
                for item in self.board.items.values()
            ],
            "preventa": [
                {**_fragment(c), "mejores_coincidencias": best(c.text, meetings, args["matches_per_point"])}
                for c in selling
            ],
            "reuniones": [
                {**_fragment(c), "mejor_preventa": (best(c.text, selling, 1) or [None])[0]} for c in meetings
            ],
        }
        return ToolResult(ok=True, content=json.dumps(report, ensure_ascii=False), metadata={"preventa": len(selling)})

    def detectar_contradicciones(self, args: dict) -> ToolResult:
        meetings = [c for c in self.retriever.all_chunks() if c.metadata.get("source_type") in MEETING_TYPES]
        pairs = []
        for index, first in enumerate(meetings):
            ranked = {r.chunk_id: r.score for r in self.retriever.search(first.text, top_k=len(meetings) + 1)}
            for second in meetings[index + 1 :]:
                score = ranked.get(second.chunk_id, 0.0)
                if score < args["min_score"]:
                    continue
                older, newer = sorted(
                    (first, second), key=lambda c: (str(c.metadata.get("source_date")), c.chunk_id)
                )
                pairs.append(
                    {
                        "similitud": round(score, 3),
                        "misma_fecha": older.metadata.get("source_date") == newer.metadata.get("source_date"),
                        "anterior": _fragment(older),
                        "posterior": _fragment(newer),
                    }
                )
        pairs.sort(key=lambda p: -p["similitud"])
        pairs = pairs[: args["top_pairs"]]
        return ToolResult(ok=True, content=json.dumps(pairs, ensure_ascii=False), metadata={"pairs": len(pairs)})

    def consultar_decisiones_vigentes(self, args: dict) -> ToolResult:
        decisions = [
            {
                "id": entry["memory_id"],
                "clave": entry["key"],
                "decision": entry["value"].get("decision"),
                "fecha": entry["value"].get("decided_on"),
                "orador": entry["value"].get("speaker"),
                "autoridad": entry["value"].get("authority"),
            }
            for entry in self.memory.current_decisions(args.get("query"))
        ]
        return ToolResult(ok=True, content=json.dumps(decisions, ensure_ascii=False), metadata={"decisions": len(decisions)})

    def approval_guard(self, context: ExecutionContext, args: dict) -> str | None:
        """Solo se escribe en la memoria con la aprobación de una persona, que pone la aplicación."""
        if not context.approved_by:
            return "Una persona debe aprobar la decisión antes de registrarla."
        return None

    def registrar_decision_aprobada(self, args: dict) -> ToolResult:
        fragment = self.retriever.get(args["fragment_id"])
        if fragment is None:
            return _fail(f"El fragmento no existe: {args['fragment_id']}", "unknown_chunk")
        if not quote_matches(args["quote"], fragment.text):
            return _fail("La frase no figura textualmente en el fragmento.", "quote_not_found")
        memory_id = self.memory.register_decision(
            args["key"],
            args["decision"],
            decided_on=date.fromisoformat(str(fragment.metadata["source_date"])),
            speaker=fragment.metadata.get("speaker") or "desconocido",
            authority=args["authority"],
            source=fragment.chunk_id,
            quote=args["quote"],
            approved_by=self.context.approved_by,
            supersedes=args.get("supersedes"),
        )
        return ToolResult(ok=True, content=f"Decisión {args['key']} registrada.", metadata={"memory_id": memory_id})

    def implementations(self) -> dict:
        return {
            "comparar_con_preventa": (self.comparar_con_preventa, CompareArgs, True),
            "detectar_contradicciones": (self.detectar_contradicciones, ContradictionArgs, True),
            "consultar_decisiones_vigentes": (self.consultar_decisiones_vigentes, DecisionsArgs, True),
            "registrar_decision_aprobada": (
                self.registrar_decision_aprobada,
                RegisterDecisionArgs,
                False,
                self.approval_guard,
            ),
        }
