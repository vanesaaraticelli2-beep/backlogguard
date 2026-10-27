"""Qué redacta el productor cuando la corrida parte del catálogo de requisitos aprobados (fuera del curso).

Una corrida ya no relee las fuentes para decidir qué hay que hacer: toma lo que una persona aprobó en «Revisión» y todavía
no está publicado (o cambió de versión desde que se publicó). El tope por corrida acota el costo; lo que queda va a la siguiente.
"""
from __future__ import annotations

from backlogguard.catalog import Requirement

MAX_REQUIREMENTS_PER_RUN = 12
MAX_QUOTES = 2
MAX_TEXT = 300

GOAL = (
    "Redactá una historia por cada requisito aprobado de la lista, y ninguna más. Para cada uno usá redactar_historia con "
    "requirement_id (RQ-nnn) y kind=historia: un título claro, la descripción y los criterios de aceptación en Gherkin. "
    "La historia hereda las citas verificadas del requisito; podés sumar otras buscando en las fuentes, pero no cambies su alcance. "
    "Si algo del requisito es ambiguo o le falta información, no lo inventes: mencionalo en tu respuesta final."
)


def pick(pending: list[Requirement]) -> tuple[list[Requirement], int]:
    """Los requisitos de esta corrida y cuántos quedan para la siguiente."""
    return pending[:MAX_REQUIREMENTS_PER_RUN], max(0, len(pending) - MAX_REQUIREMENTS_PER_RUN)


def _clip(text: str, limit: int) -> str:
    flat = " ".join(text.split())
    return flat if len(flat) <= limit else flat[: limit - 1] + "…"


def describe(requirement: Requirement) -> str:
    draft = requirement.current.draft
    lines = [f"- {requirement.id} (versión {requirement.current.number}) «{draft.title}»"]
    if draft.description:
        lines.append(f"  Detalle: {_clip(draft.description, MAX_TEXT)}")
    if draft.commitment_ids:
        lines.append(f"  Vendido en la preventa: {', '.join(draft.commitment_ids)}")
    for evidence in requirement.current.evidence[:MAX_QUOTES]:
        lines.append(f"  Se dijo: «{_clip(evidence.quote, 200)}» ({evidence.source_name})")
    return "\n".join(lines)


def goal_for(requirements: list[Requirement]) -> str:
    return f"{GOAL}\n\nRequisitos aprobados por redactar:\n" + "\n".join(describe(r) for r in requirements)
