"""Qué redacta el productor cuando la corrida parte del catálogo de requisitos aprobados (fuera del curso).

Una corrida ya no relee las fuentes para decidir qué hay que hacer: toma lo que una persona aprobó en «Revisión» y todavía
no está publicado (o cambió de versión desde que se publicó). El tope por corrida acota el costo; lo que queda va a la siguiente.
"""
from __future__ import annotations

from backlogguard.catalog import Requirement
from backlogguard.rag.retrieval import InMemoryRetriever, QdrantRetriever

MAX_REQUIREMENTS_PER_RUN = 12
MAX_QUOTES = 2
MAX_TEXT = 300
NEIGHBORS = 2  # fragmentos antes y después de cada cita, para que el productor vea todo lo que se dijo del tema
MAX_CONTEXT_CHARS = 1800

GOAL = (
    "Redactá una historia por cada requisito aprobado de la lista, y ninguna más. Para cada uno usá redactar_historia con "
    "requirement_id (RQ-nnn) y kind=historia, con `como`, `quiero` y `para` por separado, un título claro y los criterios de aceptación. "
    "Identificá TODOS los escenarios que las fuentes mencionan para ese requisito: el camino normal, los errores, los casos borde, "
    "las validaciones y las reglas. Al menos uno va como Dado/Cuando/Entonces; los demás pueden ser una regla verificable en una frase. "
    "Para eso leé el contexto de cada requisito (lo que se dijo antes y después de la cita) y, si hace falta, buscá más en las fuentes. "
    "La historia hereda las citas verificadas del requisito; no cambies su alcance ni inventes escenarios que no figuran. "
    "Si algo es ambiguo o falta información, mencionalo en tu respuesta final."
)


def pick(pending: list[Requirement]) -> tuple[list[Requirement], int]:
    """Los requisitos de esta corrida y cuántos quedan para la siguiente."""
    return pending[:MAX_REQUIREMENTS_PER_RUN], max(0, len(pending) - MAX_REQUIREMENTS_PER_RUN)


def _clip(text: str, limit: int) -> str:
    flat = " ".join(text.split())
    return flat if len(flat) <= limit else flat[: limit - 1] + "…"


def context_of(requirement: Requirement, retriever: InMemoryRetriever | QdrantRetriever | None) -> str:
    """Lo que se dijo alrededor de las citas de la reunión: los fragmentos vecinos, en orden y sin repetir."""
    if retriever is None:
        return ""
    wanted: dict[str, set[str]] = {}
    for evidence in requirement.current.evidence:
        if evidence.source_type.value != "preventa":
            wanted.setdefault(evidence.source_id, set()).add(evidence.fragment_id)
    lines: list[str] = []
    for source_id, fragment_ids in wanted.items():
        chunks = retriever.all_chunks({"document_id": source_id})
        order = [c.chunk_id for c in chunks]
        keep: set[int] = set()
        for fragment_id in fragment_ids:
            if fragment_id in order:
                at = order.index(fragment_id)
                keep.update(range(max(0, at - NEIGHBORS), min(len(order), at + NEIGHBORS + 1)))
        lines += [" ".join(chunks[i].text.split()) for i in sorted(keep)]
    return _clip(" ".join(lines), MAX_CONTEXT_CHARS)


def describe(requirement: Requirement, retriever: InMemoryRetriever | QdrantRetriever | None = None) -> str:
    draft = requirement.current.draft
    lines = [f"- {requirement.id} (versión {requirement.current.number}) «{draft.title}»"]
    if draft.description:
        lines.append(f"  Detalle: {_clip(draft.description, MAX_TEXT)}")
    if draft.commitment_ids:
        lines.append(f"  Vendido en la preventa: {', '.join(draft.commitment_ids)}")
    for evidence in requirement.current.evidence[:MAX_QUOTES]:
        lines.append(f"  Se dijo: «{_clip(evidence.quote, 200)}» ({evidence.source_name})")
    if context := context_of(requirement, retriever):
        lines.append(f"  Contexto de la reunión: {context}")
    return "\n".join(lines)


def goal_for(requirements: list[Requirement], retriever: InMemoryRetriever | QdrantRetriever | None = None) -> str:
    return f"{GOAL}\n\nRequisitos aprobados por redactar:\n" + "\n".join(describe(r, retriever) for r in requirements)
